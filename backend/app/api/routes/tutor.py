"""Tutor API routes for graph-grounded orchestration and lightweight tutoring."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.node import ConceptContextResponse
from app.schemas.tutor import (
    ProblemSolvingRequest,
    ProblemSolvingResponse,
    QuizRequest,
    QuizResponse,
    TutorAnalyzeRequest,
    TutorAnalyzeResponse,
    TutorMode,
    TutorRequest,
    TutorResponse,
    TutorSessionJumpRequest,
    TutorSessionRespondRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionsResponse,
)
from app.services.graph_service import GraphNotFoundError, NodeNotFoundError
from app.services.node_service import NodeService, get_node_service
from app.services.tutor_service import TutorService, get_tutor_service

router = APIRouter(prefix="/tutor", tags=["Tutor"])

conversations: Dict[str, Dict[str, Any]] = {}


@router.get("/concept/{concept_id}/context", response_model=ConceptContextResponse)
async def get_tutor_concept_context(
    concept_id: str,
    graphId: str,
    node_service: NodeService = Depends(get_node_service),
):
    """Return the concept context package that later tutor phases consume."""
    try:
        return node_service.get_concept_context(graphId, concept_id)
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/analyze", response_model=TutorAnalyzeResponse)
async def analyze_tutor_question(
    request: TutorAnalyzeRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Analyze a learner question against graph concepts and source evidence."""
    return tutor_service.analyze_question(request)


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

    return TutorResponse(
        message=response_message,
        conversation_id=conversation_id,
        metadata={
            "mode": request.mode,
            "message_count": len(conversation["messages"]),
            "confidence": 0.9,
        },
        suggestions=generate_suggestions(request.message),
        sources=[{"type": "knowledge_graph", "topics": extract_topics(request.message)}],
    )


@router.post("/session/start", response_model=TutorSessionResponse)
async def start_tutor_session(
    request: TutorSessionStartRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Create a step-by-step tutor session plan from a learner question."""
    return tutor_service.start_session(request)


@router.get("/sessions", response_model=TutorSessionsResponse)
async def list_tutor_sessions(
    limit: int = 50,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """List persisted tutor sessions."""
    return tutor_service.list_sessions(limit=limit)


@router.get("/session/{session_id}", response_model=TutorSessionResponse)
async def get_tutor_session(
    session_id: str,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Return the current tutor session state."""
    return tutor_service.get_session(session_id)


@router.post("/session/{session_id}/next", response_model=TutorSessionResponse)
async def advance_tutor_session(
    session_id: str,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Advance the tutor session to the next teaching step."""
    return tutor_service.advance_session(session_id)


@router.post("/session/{session_id}/respond", response_model=TutorSessionResponse)
async def respond_tutor_session(
    session_id: str,
    request: TutorSessionRespondRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Submit a learner response for the current teaching step."""
    return tutor_service.respond_to_session(session_id, request)


@router.post("/session/{session_id}/back", response_model=TutorSessionResponse)
async def back_tutor_session(
    session_id: str,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Move the tutor session back one step."""
    return tutor_service.back_session(session_id)


@router.post("/session/{session_id}/jump", response_model=TutorSessionResponse)
async def jump_tutor_session(
    session_id: str,
    request: TutorSessionJumpRequest,
    tutor_service: TutorService = Depends(get_tutor_service),
):
    """Jump to a specific step in the tutor session."""
    return tutor_service.jump_session(session_id, request)


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
                "options": ["Option A", "Option B", "Option C", "Option D"] if question_type == "multiple_choice" else None,
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


def generate_final_answer(problem: str) -> str | None:
    """Generate final answer if applicable."""
    return "Solution completed successfully"
