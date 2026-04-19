"""Tutor schemas for AI tutoring interactions."""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.node import NodeSummary


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


class CourseType(str, Enum):
    """Course planning track used by tutor session orchestration."""

    KNOWLEDGE_LEARNING = "knowledge_learning"
    PROBLEM_SOLVING = "problem_solving"


class CourseTypeStrategy(str, Enum):
    """How the final course type is selected for analyze/start requests."""

    AUTO = "auto"
    MANUAL = "manual"
    OVERRIDE = "override"


class CourseTypeDecision(BaseModel):
    """Classifier decision payload used by API metadata and observability."""

    decision: CourseType = Field(..., description="Classifier-selected course type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Decision confidence from 0 to 1")
    signals: List[str] = Field(default_factory=list, description="Signals that influenced the decision")
    overridden: bool = Field(default=False, description="Whether decision was manually overridden")


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


class ContentArtifactType(str, Enum):
    """Content artifact kinds that P3 may generate for a teaching step."""
    MARKDOWN = "markdown"
    MERMAID = "mermaid"
    LATEX = "latex"
    IMAGE = "image"
    COMIC = "comic"
    ANIMATION = "animation"
    INTERACTIVE = "interactive"


class ContentRequestResponseMode(str, Enum):
    """Whether a generated step artifact is passive or expects learner interaction."""
    PASSIVE = "passive"
    INTERACTIVE = "interactive"


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


class TutorAnalyzeRequest(BaseModel):
    """Request model for graph-grounded tutor analysis."""
    question: str = Field(..., min_length=1, description="Learner question to analyze")
    pdfId: str = Field(..., min_length=1, description="Source graph identifier")
    learnerId: Optional[str] = Field(default=None, description="Optional learner identifier for personalization")
    mode: TutorMode = Field(default=TutorMode.INTERACTIVE, description="Desired tutoring mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional learner context")
    limit: int = Field(default=3, ge=1, le=10, description="Maximum number of concept candidates to return")
    courseTypeStrategy: CourseTypeStrategy = Field(
        default=CourseTypeStrategy.AUTO,
        description="Course type selection strategy: auto/manual/override",
    )
    courseTypeOverride: Optional[CourseType] = Field(
        default=None,
        description="Optional manual course type when strategy is manual/override",
    )
    courseType: Optional[CourseType] = Field(
        default=None,
        description="Legacy compatibility field mapped to courseTypeOverride",
    )

    @model_validator(mode="after")
    def _normalize_course_type_fields(self):
        if self.courseTypeOverride is None and self.courseType is not None:
            self.courseTypeOverride = self.courseType
        return self


class TutorEvidencePassage(BaseModel):
    """Sentence-level evidence excerpt ranked for tutor orchestration."""
    chunkId: str = Field(..., description="Source chunk identifier")
    conceptId: str = Field(..., description="Related concept identifier")
    conceptLabel: str = Field(..., description="Related concept label")
    sourceFile: str = Field(..., description="Source file path relative to the graph root")
    sourceLocation: Optional[str] = Field(default=None, description="Source location carried from Graphify")
    pageStart: Optional[int] = Field(default=None, description="Starting page number when available")
    pageEnd: Optional[int] = Field(default=None, description="Ending page number when available")
    excerpt: str = Field(..., min_length=1, description="Sentence-level excerpt selected from the chunk")
    score: float = Field(..., description="Ranking score for the excerpt")


class TutorAnalyzeConcept(BaseModel):
    """Concept candidate returned by tutor analyze."""
    node: NodeSummary = Field(..., description="Matched graph node")
    matchScore: float = Field(..., description="Semantic search score")
    summary: str = Field(..., description="Compact summary of why the concept matters")
    prerequisitesCount: int = Field(default=0, description="Number of prerequisite concepts")
    relatedCount: int = Field(default=0, description="Number of related concepts")


class TutorAnalyzeResponse(BaseModel):
    """Graph-grounded analysis result used before starting a session."""
    graphId: str = Field(..., description="Graph identifier")
    question: str = Field(..., description="Original learner question")
    summary: str = Field(..., description="Analysis summary")
    relevantConcepts: List[TutorAnalyzeConcept] = Field(default_factory=list, description="Matched graph concepts")
    highlightedNodeIds: List[str] = Field(default_factory=list, description="Node ids to highlight in the graph view")
    evidencePassages: List[TutorEvidencePassage] = Field(default_factory=list, description="Ranked evidence excerpts from source passages")
    suggestedSession: Dict[str, Any] = Field(default_factory=dict, description="Suggested session bootstrap metadata")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional analysis metadata")


class TeachingContentRequest(BaseModel):
    """Stable step-level content generation contract handed to P3."""
    stage: TeachingStepType = Field(..., description="Teaching stage that the content generator should serve")
    stepId: str = Field(..., min_length=1, description="Stable teaching step identifier")
    stepTitle: str = Field(..., min_length=1, description="Human-readable step title")
    objective: str = Field(..., min_length=1, description="Instructional objective for the content artifact")
    question: str = Field(..., min_length=1, description="Original learner question for the whole session")
    graphId: str = Field(..., min_length=1, description="Source graph identifier that grounds this request")
    sessionMode: TutorMode = Field(..., description="Tutor mode that shaped the teaching plan")
    learnerLevel: str = Field(..., min_length=1, description="Learner level hint carried from session context")
    responseMode: ContentRequestResponseMode = Field(..., description="Whether the generated artifact is passive or interactive")
    primaryConceptId: Optional[str] = Field(default=None, description="Primary concept selected during tutor analyze")
    conceptIds: List[str] = Field(default_factory=list, description="Concept ids available to content generation")
    highlightedNodeIds: List[str] = Field(default_factory=list, description="Graph node ids the UI should highlight for this step")
    evidencePassageIds: List[str] = Field(default_factory=list, description="Source passage chunk ids relevant to this step")
    targetContentTypes: List[ContentArtifactType] = Field(
        default_factory=lambda: [ContentArtifactType.MARKDOWN],
        description="Requested artifact kinds for downstream content generation",
    )
    renderHint: ContentArtifactType = Field(
        default=ContentArtifactType.MARKDOWN,
        description="Primary content type that current consumers should prefer rendering first",
    )


class TeachingStepContent(BaseModel):
    """Structured step payload combining current placeholders and future content inputs."""

    model_config = ConfigDict(extra="allow")

    markdown: Optional[str] = Field(default=None, description="Current markdown placeholder shown before P3 artifacts exist")
    guidingQuestion: Optional[str] = Field(default=None, description="Optional learner-facing guiding question")
    prompt: Optional[str] = Field(default=None, description="Optional prompt for practice or quiz style steps")
    nextActions: List[str] = Field(default_factory=list, description="Optional follow-up actions for summary style steps")
    graphHighlights: List[str] = Field(default_factory=list, description="Graph node ids to emphasize in the UI")
    evidencePassages: List[TutorEvidencePassage] = Field(
        default_factory=list,
        description="Evidence excerpts that anchor the current teaching step",
    )
    contentRequest: Optional[TeachingContentRequest] = Field(
        default=None,
        description="Stable request payload that P3 should consume to generate artifacts",
    )
    contentArtifactId: Optional[str] = Field(
        default=None,
        description="Generated content artifact id for the current teaching step",
    )
    contentArtifactStatus: Optional[str] = Field(
        default=None,
        description="Artifact status snapshot for the current step",
    )
    contentArtifactUpdatedAt: Optional[str] = Field(
        default=None,
        description="Artifact timestamp surfaced to frontend consumers",
    )


class ModalityPlan(BaseModel):
    """Per-step modality strategy used by downstream renderers and generators."""

    primary: ContentArtifactType = Field(..., description="Primary artifact type for the current step")
    secondary: List[ContentArtifactType] = Field(
        default_factory=list,
        description="Optional secondary artifact types for richer delivery",
    )
    responseMode: ContentRequestResponseMode = Field(
        default=ContentRequestResponseMode.PASSIVE,
        description="Whether this step is passive or interactive from learner perspective",
    )
    interactionMode: str = Field(default="guided", description="Interaction style hint for UI/runtime")
    rationale: str = Field(..., min_length=1, description="Why this modality mix was selected")


class CheckpointSpec(BaseModel):
    """Structured checkpoint contract for response-required teaching steps."""

    checkpointId: str = Field(..., min_length=1, description="Stable checkpoint identifier")
    kind: str = Field(..., min_length=1, description="Checkpoint type such as concept_check or transfer_check")
    prompt: str = Field(..., min_length=1, description="Prompt that defines the checkpoint objective")
    expectedEvidence: List[str] = Field(
        default_factory=list,
        description="Signals/rubric bullets expected from learner response",
    )
    passThreshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Passing threshold for checkpoint scoring")
    retryHint: str = Field(default="restate key concept and retry", description="Hint shown when learner response is weak")


class TeachingStep(BaseModel):
    """Single step inside a tutor session plan"""
    id: str = Field(..., description="Unique step identifier")
    type: TeachingStepType = Field(..., description="Step type")
    title: str = Field(..., min_length=1, description="Step title")
    objective: str = Field(..., min_length=1, description="Instructional objective")
    content: TeachingStepContent = Field(default_factory=TeachingStepContent, description="Structured rendering payload")
    modalityPlan: ModalityPlan = Field(
        default_factory=lambda: ModalityPlan(
            primary=ContentArtifactType.MARKDOWN,
            secondary=[],
            responseMode=ContentRequestResponseMode.PASSIVE,
            interactionMode="guided",
            rationale="default_modality_plan",
        ),
        description="Per-step modality delivery plan",
    )
    checkpointSpec: Optional[CheckpointSpec] = Field(
        default=None,
        description="Optional checkpoint scoring contract for key response-required steps",
    )
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
                    "graphHighlights": ["目标值", "误差", "反馈"],
                    "contentRequest": {
                        "stage": "intro",
                        "stepId": "step-1",
                        "stepTitle": "建立问题背景",
                        "objective": "明确学习目标与关键概念",
                        "question": "Explain PID controllers",
                        "graphId": "graph-task-123",
                        "sessionMode": "interactive",
                        "learnerLevel": "beginner",
                        "responseMode": "passive",
                        "primaryConceptId": "concept-pid",
                        "conceptIds": ["concept-pid"],
                        "highlightedNodeIds": ["concept-pid"],
                        "evidencePassageIds": ["chunk-pid-1"],
                        "targetContentTypes": ["markdown"],
                        "renderHint": "markdown"
                    }
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
    planFinalized: bool = Field(default=True, description="Whether the plan has been fully materialized and frozen")

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
    learnerId: Optional[str] = Field(default=None, description="Optional learner identifier for progress tracking")
    mode: TutorMode = Field(default=TutorMode.INTERACTIVE, description="Desired tutoring mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional learning context")
    courseTypeStrategy: CourseTypeStrategy = Field(
        default=CourseTypeStrategy.AUTO,
        description="Course type selection strategy: auto/manual/override",
    )
    courseTypeOverride: Optional[CourseType] = Field(
        default=None,
        description="Optional manual course type when strategy is manual/override",
    )
    courseType: Optional[CourseType] = Field(
        default=None,
        description="Legacy compatibility field mapped to courseTypeOverride",
    )

    @model_validator(mode="after")
    def _normalize_course_type_fields(self):
        if self.courseTypeOverride is None and self.courseType is not None:
            self.courseTypeOverride = self.courseType
        return self

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


class TutorSessionJumpRequest(BaseModel):
    """Jump to a specific step in the tutor session."""
    stepIndex: Optional[int] = Field(default=None, ge=0, description="Target zero-based step index")
    stepId: Optional[str] = Field(default=None, description="Target step identifier")


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


class TutorSessionListItem(BaseModel):
    """Summary row returned by the session listing endpoint."""
    sessionId: str = Field(..., description="Session identifier")
    question: str = Field(..., description="Original learner question")
    pdfId: str = Field(..., description="Source graph identifier")
    mode: str = Field(..., description="Tutor mode")
    status: str = Field(..., description="Current session status")
    currentStepIndex: int = Field(default=-1, description="Current step index")
    currentStepTitle: Optional[str] = Field(default=None, description="Current step title when available")
    topics: List[str] = Field(default_factory=list, description="Topics associated with the session")
    updatedAt: str = Field(..., description="Last updated timestamp")


class TutorSessionsResponse(BaseModel):
    """List response for stored tutor sessions."""
    items: List[TutorSessionListItem] = Field(default_factory=list, description="Stored session summaries")
    total: int = Field(default=0, description="Total returned sessions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Listing metadata")


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
