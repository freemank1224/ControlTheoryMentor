"""
Tutor schemas for AI tutoring interactions
"""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message role types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TutorMode(str, Enum):
    """Tutor interaction modes"""
    INTERACTIVE = "interactive"
    TUTORIAL = "tutorial"
    QUIZ = "quiz"
    PROBLEM_SOLVING = "problem_solving"


class TutorSessionStatus(str, Enum):
    """Step-by-step tutor session states"""
    READY = "ready"
    IN_PROGRESS = "in_progress"
    AWAITING_RESPONSE = "awaiting_response"
    COMPLETED = "completed"


class TeachingStepType(str, Enum):
    """Supported teaching step types"""
    INTRO = "intro"
    CONCEPT = "concept"
    CHECKPOINT = "checkpoint"
    PRACTICE = "practice"
    SUMMARY = "summary"


class TutorMessage(BaseModel):
    """Individual message in a conversation"""
    role: MessageType = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Explain PID controllers",
                "metadata": {}
            }
        }


class TutorRequest(BaseModel):
    """Request model for tutor interaction"""
    message: str = Field(..., min_length=1, description="User message or question")
    mode: TutorMode = Field(default=TutorMode.INTERACTIVE, description="Tutoring mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Learning context")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for continuity")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Explain transfer functions",
                "mode": "interactive",
                "context": {
                    "current_topic": "control systems",
                    "learning_level": "beginner"
                },
                "conversation_id": "conv-123"
            }
        }


class TutorResponse(BaseModel):
    """Response model for tutor interaction"""
    message: str = Field(..., min_length=1, description="Tutor response")
    conversation_id: str = Field(..., description="Conversation ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    suggestions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source references")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "PID controllers are used to control systems...",
                "conversation_id": "conv-123",
                "metadata": {
                    "confidence": 0.95,
                    "topics_covered": ["PID", "control systems"]
                },
                "suggestions": [
                    "Tell me more about proportional control",
                    "How do I tune a PID controller?"
                ],
                "sources": [
                    {
                        "type": "textbook",
                        "title": "Modern Control Engineering",
                        "page": 42
                    }
                ]
            }
        }


class TeachingStep(BaseModel):
    """Single step inside a tutor session plan"""
    id: str = Field(..., description="Unique step identifier")
    type: TeachingStepType = Field(..., description="Step type")
    title: str = Field(..., min_length=1, description="Step title")
    objective: str = Field(..., min_length=1, description="Instructional objective")
    content: Dict[str, Any] = Field(default_factory=dict, description="Structured rendering payload")
    relatedTopics: List[str] = Field(default_factory=list, description="Knowledge graph topics referenced by the step")
    requiresResponse: bool = Field(default=False, description="Whether the learner must respond before advancing")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "step-1",
                "type": "intro",
                "title": "建立问题背景",
                "objective": "明确学习目标与关键概念",
                "content": {
                    "markdown": "我们先把 PID 控制器放回闭环控制场景里。",
                    "highlights": ["目标值", "误差", "反馈"]
                },
                "relatedTopics": ["pid", "feedback"],
                "requiresResponse": False
            }
        }


class TeachingPlan(BaseModel):
    """Session plan returned when a tutor session starts"""
    summary: str = Field(..., min_length=1, description="High-level plan summary")
    goals: List[str] = Field(default_factory=list, description="Learning goals for the session")
    steps: List[TeachingStep] = Field(default_factory=list, description="Ordered teaching steps")

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "从概念建立到理解检查再到迁移练习的四步教学计划。",
                "goals": ["识别 PID 三项作用", "知道何时使用反馈"],
                "steps": []
            }
        }


class TutorSessionStartRequest(BaseModel):
    """Start a new step-by-step tutor session"""
    question: str = Field(..., min_length=1, description="Learner question that seeds the session")
    pdfId: str = Field(..., min_length=1, description="Source PDF or graph identifier")
    mode: TutorMode = Field(default=TutorMode.INTERACTIVE, description="Desired tutoring mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional learning context")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "mode": "interactive",
                "context": {
                    "learning_level": "beginner",
                    "chapter": "Chapter 4"
                }
            }
        }


class TutorSessionRespondRequest(BaseModel):
    """Respond to the current interactive session step"""
    response: str = Field(..., min_length=1, description="Learner response to the current tutor prompt")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional response metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "P handles immediate error, I removes steady-state error, D damps fast changes.",
                "metadata": {
                    "confidence": "medium"
                }
            }
        }


class TutorSessionResponse(BaseModel):
    """Current state of a step-by-step tutor session"""
    sessionId: str = Field(..., description="Unique tutor session identifier")
    plan: TeachingPlan = Field(..., description="Ordered teaching plan")
    currentStep: Optional[TeachingStep] = Field(default=None, description="Currently active teaching step")
    currentStepIndex: int = Field(default=-1, description="Zero-based current step index")
    status: TutorSessionStatus = Field(..., description="Current tutor session status")
    messages: List[TutorMessage] = Field(default_factory=list, description="Accumulated tutor dialogue during the session")
    canAdvance: bool = Field(default=True, description="Whether the learner can call the next step endpoint")
    needsUserResponse: bool = Field(default=False, description="Whether the current step requires a learner response")
    feedback: Optional[str] = Field(default=None, description="Most recent tutor feedback")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "sessionId": "session-123",
                "plan": {
                    "summary": "围绕 PID 问题的四步学习计划",
                    "goals": ["理解三项作用"],
                    "steps": []
                },
                "currentStep": None,
                "currentStepIndex": -1,
                "status": "ready",
                "messages": [],
                "canAdvance": True,
                "needsUserResponse": False,
                "feedback": None,
                "metadata": {
                    "pdfId": "graph-task-123"
                }
            }
        }


class QuizRequest(BaseModel):
    """Request model for quiz generation"""
    topic: str = Field(..., min_length=1, description="Quiz topic")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    question_count: int = Field(default=5, ge=1, le=20, description="Number of questions")
    question_types: List[str] = Field(
        default_factory=lambda: ["multiple_choice", "true_false"],
        description="Types of questions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "PID Controllers",
                "difficulty": "medium",
                "question_count": 5,
                "question_types": ["multiple_choice", "true_false", "short_answer"]
            }
        }


class QuizResponse(BaseModel):
    """Response model for quiz generation"""
    quiz_id: str = Field(..., description="Unique quiz identifier")
    questions: List[Dict[str, Any]] = Field(..., description="Quiz questions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Quiz metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "quiz_id": "quiz-123",
                "questions": [
                    {
                        "id": "q1",
                        "type": "multiple_choice",
                        "question": "What does P stand for in PID?",
                        "options": ["Proportional", "Integral", "Derivative", "Power"],
                        "correct_answer": "Proportional"
                    }
                ],
                "metadata": {
                    "topic": "PID Controllers",
                    "difficulty": "medium",
                    "estimated_time_minutes": 10
                }
            }
        }


class ProblemSolvingRequest(BaseModel):
    """Request model for problem-solving help"""
    problem_statement: str = Field(..., min_length=1, description="Problem to solve")
    subject: str = Field(..., description="Subject area")
    hints_requested: int = Field(default=1, ge=0, le=5, description="Number of hints requested")

    class Config:
        json_schema_extra = {
            "example": {
                "problem_statement": "Design a PID controller for a system with transfer function G(s) = 1/(s+1)",
                "subject": "control systems",
                "hints_requested": 2
            }
        }


class ProblemSolvingResponse(BaseModel):
    """Response model for problem-solving help"""
    solution_steps: List[str] = Field(..., description="Step-by-step solution")
    hints: List[str] = Field(default_factory=list, description="Hints provided")
    final_answer: Optional[str] = Field(default=None, description="Final answer")
    explanation: str = Field(..., description="Detailed explanation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Solution metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "solution_steps": [
                    "Identify the system type",
                    "Determine the desired specifications",
                    "Calculate PID parameters"
                ],
                "hints": [
                    "Start by analyzing the system's open-loop response",
                    "Consider using Ziegler-Nichols tuning method"
                ],
                "final_answer": "Kp=2.0, Ki=1.0, Kd=0.5",
                "explanation": "The PID controller parameters were calculated...",
                "metadata": {
                    "confidence": 0.9,
                    "subject": "control systems"
                }
            }
        }
