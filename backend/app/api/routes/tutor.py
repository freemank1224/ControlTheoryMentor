"""Tutor API routes for AI tutoring interactions."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.schemas.tutor import (
    MessageType,
    ProblemSolvingRequest,
    ProblemSolvingResponse,
    QuizRequest,
    QuizResponse,
    TeachingPlan,
    TeachingStep,
    TeachingStepType,
    TutorMessage,
    TutorMode,
    TutorRequest,
    TutorResponse,
    TutorSessionRespondRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionStatus,
)

router = APIRouter(prefix="/tutor", tags=["Tutor"])

# In-memory storage for conversations and tutor sessions.
conversations: Dict[str, Dict[str, Any]] = {}
tutor_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/chat", response_model=TutorResponse)
async def tutor_chat(request: TutorRequest):
    """Interact with the lightweight tutor chat endpoint."""
    if request.conversation_id:
        if request.conversation_id not in conversations:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation_id = request.conversation_id
        conversation = conversations[conversation_id]
    else:
        conversation_id = f"conv-{uuid.uuid4()}"
        conversation = {
            "id": conversation_id,
            "messages": [],
            "context": request.context or {},
        }
        conversations[conversation_id] = conversation

    conversation["messages"].append({"role": "user", "content": request.message})

    response_message = generate_tutor_response(request.message, request.mode, conversation)

    conversation["messages"].append({"role": "assistant", "content": response_message})

    suggestions = generate_suggestions(request.message)

    return TutorResponse(
        message=response_message,
        conversation_id=conversation_id,
        metadata={
            "mode": request.mode,
            "message_count": len(conversation["messages"]),
            "confidence": 0.9,
        },
        suggestions=suggestions,
        sources=[{"type": "knowledge_graph", "topics": extract_topics(request.message)}],
    )


@router.post("/session/start", response_model=TutorSessionResponse)
async def start_tutor_session(request: TutorSessionStartRequest):
    """Create a step-by-step tutor session plan from a learner question."""
    session_id = f"session-{uuid.uuid4()}"
    topics = extract_topics(request.question)
    plan = build_teaching_plan(request.question, request.mode, topics, request.context or {})
    now = utc_now_iso()

    tutor_sessions[session_id] = {
        "id": session_id,
        "question": request.question,
        "pdfId": request.pdfId,
        "mode": request.mode,
        "context": request.context or {},
        "topics": topics,
        "plan": plan,
        "messages": [
            TutorMessage(
                role=MessageType.SYSTEM,
                content=f"Tutor session started for question: {request.question}",
                metadata={
                    "event": "session_started",
                    "pdfId": request.pdfId,
                    "topics": topics,
                },
            )
        ],
        "currentStepIndex": -1,
        "status": TutorSessionStatus.READY,
        "awaitingResponse": False,
        "createdAt": now,
        "updatedAt": now,
    }

    return build_session_response(tutor_sessions[session_id])


@router.get("/session/{session_id}", response_model=TutorSessionResponse)
async def get_tutor_session(session_id: str):
    """Return the current tutor session state."""
    session = get_session_or_404(session_id)
    return build_session_response(session)


@router.post("/session/{session_id}/next", response_model=TutorSessionResponse)
async def advance_tutor_session(session_id: str):
    """Advance the tutor session to the next teaching step."""
    session = get_session_or_404(session_id)
    plan: TeachingPlan = session["plan"]

    if session["status"] == TutorSessionStatus.COMPLETED:
        return build_session_response(session, feedback="This session is already complete.")

    if session["awaitingResponse"]:
        raise HTTPException(
            status_code=409,
            detail="Current step requires a learner response before advancing.",
        )

    next_index = session["currentStepIndex"] + 1
    if next_index >= len(plan.steps):
        session["status"] = TutorSessionStatus.COMPLETED
        session["currentStepIndex"] = len(plan.steps)
        completion_message = build_completion_message(session)
        session["messages"].append(
            TutorMessage(
                role=MessageType.ASSISTANT,
                content=completion_message,
                metadata={"event": "session_completed"},
            )
        )
        touch_session(session)
        return build_session_response(session, feedback=completion_message)

    step = plan.steps[next_index]
    session["currentStepIndex"] = next_index
    session["awaitingResponse"] = step.requiresResponse
    session["status"] = (
        TutorSessionStatus.AWAITING_RESPONSE
        if step.requiresResponse
        else TutorSessionStatus.IN_PROGRESS
    )
    session["messages"].append(
        TutorMessage(
            role=MessageType.ASSISTANT,
            content=render_step_message(step, session),
            metadata={
                "event": "step_started",
                "stepId": step.id,
                "stepType": step.type,
            },
        )
    )
    touch_session(session)
    return build_session_response(session)


@router.post("/session/{session_id}/respond", response_model=TutorSessionResponse)
async def respond_tutor_session(session_id: str, request: TutorSessionRespondRequest):
    """Submit a learner response for the current teaching step."""
    session = get_session_or_404(session_id)
    plan: TeachingPlan = session["plan"]
    current_index = session["currentStepIndex"]

    if current_index < 0 or current_index >= len(plan.steps):
        raise HTTPException(status_code=409, detail="No active teaching step to respond to.")

    if not session["awaitingResponse"]:
        raise HTTPException(status_code=409, detail="Current step does not require a learner response.")

    current_step = plan.steps[current_index]
    session["messages"].append(
        TutorMessage(
            role=MessageType.USER,
            content=request.response,
            metadata={
                "event": "step_response",
                "stepId": current_step.id,
                **request.metadata,
            },
        )
    )

    feedback = generate_step_feedback(current_step, request.response, session)
    session["messages"].append(
        TutorMessage(
            role=MessageType.ASSISTANT,
            content=feedback,
            metadata={
                "event": "step_feedback",
                "stepId": current_step.id,
            },
        )
    )
    session["awaitingResponse"] = False

    if current_index >= len(plan.steps) - 1:
        session["status"] = TutorSessionStatus.COMPLETED
        completion_message = build_completion_message(session)
        session["messages"].append(
            TutorMessage(
                role=MessageType.ASSISTANT,
                content=completion_message,
                metadata={"event": "session_completed"},
            )
        )
        touch_session(session)
        return build_session_response(session, feedback=feedback)

    session["status"] = TutorSessionStatus.READY
    touch_session(session)
    return build_session_response(session, feedback=feedback)


@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(request: QuizRequest):
    """Generate a quiz on a specific topic."""
    quiz_id = f"quiz-{uuid.uuid4()}"
    questions = generate_quiz_questions(
        request.topic,
        request.difficulty,
        request.question_count,
        request.question_types,
    )

    return QuizResponse(
        quiz_id=quiz_id,
        questions=questions,
        metadata={
            "topic": request.topic,
            "difficulty": request.difficulty,
            "question_count": len(questions),
            "estimated_time_minutes": len(questions) * 2,
        },
    )


@router.post("/solve", response_model=ProblemSolvingResponse)
async def solve_problem(request: ProblemSolvingRequest):
    """Get help solving a problem."""
    solution_steps = generate_solution_steps(request.problem_statement)
    hints = []
    if request.hints_requested > 0:
        hints = generate_hints(request.problem_statement, request.hints_requested)

    explanation = generate_explanation(request.problem_statement, solution_steps)
    final_answer = generate_final_answer(request.problem_statement)

    return ProblemSolvingResponse(
        solution_steps=solution_steps,
        hints=hints,
        final_answer=final_answer,
        explanation=explanation,
        metadata={
            "subject": request.subject,
            "confidence": 0.85,
            "complexity": "medium",
        },
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = conversations[conversation_id]
    return {
        "id": conversation_id,
        "messages": conversation["messages"],
        "context": conversation.get("context", {}),
        "metadata": {
            "message_count": len(conversation["messages"]),
            "created_at": "2026-04-18T00:00:00Z",
        },
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    del conversations[conversation_id]
    return {"message": "Conversation deleted successfully"}


def utc_now_iso() -> str:
    """Return an ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def touch_session(session: Dict[str, Any]) -> None:
    """Update the session modification timestamp."""
    session["updatedAt"] = utc_now_iso()


def get_session_or_404(session_id: str) -> Dict[str, Any]:
    """Return a tutor session or raise a 404."""
    if session_id not in tutor_sessions:
        raise HTTPException(status_code=404, detail="Tutor session not found")
    return tutor_sessions[session_id]


def build_session_response(session: Dict[str, Any], feedback: str | None = None) -> TutorSessionResponse:
    """Serialize in-memory tutor session state into the API response shape."""
    plan: TeachingPlan = session["plan"]
    current_step_index = session["currentStepIndex"]
    current_step = None
    if 0 <= current_step_index < len(plan.steps):
        current_step = plan.steps[current_step_index]

    return TutorSessionResponse(
        sessionId=session["id"],
        plan=plan,
        currentStep=current_step,
        currentStepIndex=current_step_index,
        status=session["status"],
        messages=session["messages"],
        canAdvance=(
            session["status"] != TutorSessionStatus.COMPLETED and not session["awaitingResponse"]
        ),
        needsUserResponse=session["awaitingResponse"],
        feedback=feedback,
        metadata={
            "pdfId": session["pdfId"],
            "question": session["question"],
            "mode": session["mode"],
            "topics": session["topics"],
            "totalSteps": len(plan.steps),
            "createdAt": session["createdAt"],
            "updatedAt": session["updatedAt"],
        },
    )


def build_teaching_plan(
    question: str,
    mode: TutorMode,
    topics: List[str],
    context: Dict[str, Any],
) -> TeachingPlan:
    """Create a deterministic step-by-step tutoring plan from a user question."""
    primary_topic = topics[0] if topics else "control theory"
    learner_level = str(context.get("learning_level", "intermediate"))
    chapter_hint = context.get("chapter")

    steps = [
        TeachingStep(
            id="step-1",
            type=TeachingStepType.INTRO,
            title=f"建立问题背景: {primary_topic}",
            objective="明确本次学习的目标、范围与图谱关注点。",
            content={
                "markdown": (
                    f"我们先把问题“{question}”放回控制理论语境中，明确它和 {primary_topic}、"
                    "反馈结构、系统目标之间的关系。"
                ),
                "highlights": topics,
                "learnerLevel": learner_level,
                "chapterHint": chapter_hint,
            },
            relatedTopics=topics,
            requiresResponse=False,
        ),
        TeachingStep(
            id="step-2",
            type=TeachingStepType.CONCEPT,
            title=f"拆解核心概念: {primary_topic}",
            objective="把核心概念拆成更容易验证理解的要点。",
            content={
                "markdown": (
                    f"现在拆解 {primary_topic} 的关键组成、作用和常见误区，"
                    "把抽象概念变成几个可回答的判断点。"
                ),
                "guidingQuestion": f"用你自己的话描述 {primary_topic} 在控制系统中的作用。",
            },
            relatedTopics=topics,
            requiresResponse=True,
        ),
        TeachingStep(
            id="step-3",
            type=TeachingStepType.PRACTICE if mode != TutorMode.QUIZ else TeachingStepType.CHECKPOINT,
            title="理解检查与迁移",
            objective="验证能否将概念迁移到一个更具体的问题场景。",
            content={
                "markdown": build_practice_markdown(mode, primary_topic),
                "prompt": build_practice_prompt(mode, primary_topic),
            },
            relatedTopics=topics,
            requiresResponse=True,
        ),
        TeachingStep(
            id="step-4",
            type=TeachingStepType.SUMMARY,
            title="总结与下一步",
            objective="收束本轮学习，并给出下一步推荐。",
            content={
                "markdown": (
                    "最后我们把今天的关键结论收束成可复述的知识点，"
                    "并给出下一步继续学习的建议。"
                ),
                "nextActions": [
                    f"回看与 {primary_topic} 相关的图谱节点",
                    "补做一个具体例题或参数分析练习",
                    "继续追问和当前主题最相关的前置概念",
                ],
            },
            relatedTopics=topics,
            requiresResponse=False,
        ),
    ]

    mode_label = {
        TutorMode.INTERACTIVE: "交互式理解",
        TutorMode.TUTORIAL: "讲解式教学",
        TutorMode.QUIZ: "测验式学习",
        TutorMode.PROBLEM_SOLVING: "解题式辅导",
    }[mode]

    return TeachingPlan(
        summary=f"围绕“{question}”的 {mode_label} 四步教学计划。",
        goals=[
            f"识别 {primary_topic} 的核心作用",
            "能用自己的话复述关键概念",
            "能把概念迁移到一个更具体的控制场景里",
        ],
        steps=steps,
    )


def build_practice_markdown(mode: TutorMode, primary_topic: str) -> str:
    """Return mode-aware practice step content."""
    if mode == TutorMode.QUIZ:
        return f"进入快速检查：判断你是否已经能区分 {primary_topic} 的功能、限制和适用场景。"
    if mode == TutorMode.PROBLEM_SOLVING:
        return f"把 {primary_topic} 放入一个具体求解场景，说明你会先抓哪些变量与约束。"
    return f"把 {primary_topic} 应用到一个更具体的系统或情境中，看看理解是否能迁移。"


def build_practice_prompt(mode: TutorMode, primary_topic: str) -> str:
    """Return a learner prompt for the practice step."""
    if mode == TutorMode.QUIZ:
        return f"给出一个简短判断：什么时候 {primary_topic} 会失效或不再适用？"
    if mode == TutorMode.PROBLEM_SOLVING:
        return f"如果你要基于 {primary_topic} 解题，请先列出最关键的两个已知量和一个目标量。"
    return f"请举一个你会用到 {primary_topic} 的实际或教材场景，并说明原因。"


def render_step_message(step: TeachingStep, session: Dict[str, Any]) -> str:
    """Render the tutor narration for a newly activated step."""
    question = session["question"]
    base = f"[{step.title}] {step.content.get('markdown', '')}"
    if step.requiresResponse:
        prompt = step.content.get("guidingQuestion") or step.content.get("prompt")
        return f"{base}\n\n请基于你的问题“{question}”回答：{prompt}"
    return base


def generate_step_feedback(step: TeachingStep, response: str, session: Dict[str, Any]) -> str:
    """Produce deterministic feedback for a learner response."""
    concise = response.strip()
    word_count = len([part for part in concise.replace("\n", " ").split(" ") if part])
    primary_topic = session["topics"][0] if session["topics"] else "the topic"

    if word_count < 6:
        return (
            f"你的回答已经抓住了一部分方向，但还比较简略。"
            f"建议再补一句：{primary_topic} 影响了系统的哪个行为，以及为什么。"
        )

    return (
        f"你的回答已经把 {step.title} 里的关键点说出来了。"
        f"下一步可以继续检查你是否能把 {primary_topic} 放进具体系统场景里使用。"
    )


def build_completion_message(session: Dict[str, Any]) -> str:
    """Return the tutor session completion summary."""
    primary_topic = session["topics"][0] if session["topics"] else "control theory"
    return (
        f"本轮关于 {primary_topic} 的教学会话已经完成。"
        "你现在可以回到知识图谱继续追踪相关节点，或者围绕同一主题发起下一轮更深入的问题。"
    )


def generate_tutor_response(message: str, mode: TutorMode, conversation: Dict[str, Any]) -> str:
    """Generate tutor response based on message and mode."""
    responses = {
        TutorMode.INTERACTIVE: f"Let me help you understand: {message}. This is an important concept in control theory.",
        TutorMode.TUTORIAL: f"Here's a tutorial on: {message}. We'll break this down step by step.",
        TutorMode.QUIZ: f"Let's test your knowledge about: {message}. Here are some questions...",
        TutorMode.PROBLEM_SOLVING: f"To solve this problem about {message}, we need to follow these steps...",
    }
    return responses.get(mode, responses[TutorMode.INTERACTIVE])


def generate_suggestions(message: str) -> List[str]:
    """Generate follow-up suggestions."""
    suggestions = [
        "Can you explain that in simpler terms?",
        "Give me a practical example",
        "How does this relate to control systems?",
        "What are the key assumptions?",
    ]
    return suggestions[:3]


def extract_topics(message: str) -> List[str]:
    """Extract topics from message using simple keyword matching."""
    topics = []
    message_lower = message.lower()
    control_topics = [
        "pid",
        "feedback",
        "stability",
        "transfer function",
        "frequency response",
        "root locus",
        "state space",
    ]

    for topic in control_topics:
        if topic in message_lower:
            topics.append(topic)

    return topics if topics else ["control theory"]


def generate_quiz_questions(topic: str, difficulty: str, count: int, types: List[str]) -> List[Dict[str, Any]]:
    """Generate quiz questions."""
    questions = []
    for i in range(count):
        question_type = types[i % len(types)]
        questions.append(
            {
                "id": f"q{i+1}",
                "type": question_type,
                "question": f"Question {i+1} about {topic}",
                "options": ["Option A", "Option B", "Option C", "Option D"]
                if question_type == "multiple_choice"
                else None,
                "correct_answer": "Option A" if question_type == "multiple_choice" else "True",
                "points": 10,
            }
        )
    return questions


def generate_solution_steps(problem: str) -> List[str]:
    """Generate solution steps."""
    return [
        "Analyze the problem statement",
        "Identify key variables and parameters",
        "Apply relevant control theory principles",
        "Calculate the required parameters",
        "Verify the solution",
    ]


def generate_hints(problem: str, count: int) -> List[str]:
    """Generate hints for problem solving."""
    hints = [
        "Start by identifying the system type",
        "Consider the control objectives",
        "Think about stability criteria",
        "Recall the standard control methods",
    ]
    return hints[:count]


def generate_explanation(problem: str, steps: List[str]) -> str:
    """Generate detailed explanation."""
    return f"To solve this problem about '{problem}', we follow these steps: " + ", ".join(steps)


def generate_final_answer(problem: str) -> Optional[str]:
    """Generate final answer if applicable."""
    return "Solution completed successfully"
