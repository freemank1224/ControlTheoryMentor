"""Learning loop schemas for P4 progress and feedback APIs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LearningEventType(str, Enum):
    """Supported learning events tracked across tutor sessions."""

    SESSION_STARTED = "session_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_RESPONSE = "step_response"
    CONTENT_VIEWED = "content_viewed"
    SESSION_COMPLETED = "session_completed"


class MasteryLevel(str, Enum):
    """Normalized mastery buckets derived from concept scores."""

    NOT_STARTED = "not_started"
    DEVELOPING = "developing"
    PRACTICING = "practicing"
    MASTERED = "mastered"


class FeedbackDifficulty(str, Enum):
    """Learner-perceived difficulty for generated content and pacing."""

    TOO_EASY = "too_easy"
    APPROPRIATE = "appropriate"
    TOO_HARD = "too_hard"


class LearningEventRecord(BaseModel):
    """Single persisted event used to build progress timelines."""

    id: str = Field(..., description="Unique event identifier")
    eventType: LearningEventType = Field(..., description="Tracked event type")
    timestamp: str = Field(..., description="Event timestamp")
    sessionId: str | None = Field(default=None, description="Related tutor session id")
    stepId: str | None = Field(default=None, description="Related tutor step id")
    conceptId: str | None = Field(default=None, description="Related concept id when available")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Optional learner confidence")
    masteryDelta: float = Field(default=0.0, ge=-1.0, le=1.0, description="Applied mastery delta")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")


class ConceptMasteryState(BaseModel):
    """Current mastery snapshot for a concept."""

    conceptId: str = Field(..., description="Concept node id")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized mastery score")
    level: MasteryLevel = Field(..., description="Mastery level bucket")
    updatedAt: str = Field(..., description="Last update timestamp")


class LearningFeedbackEntry(BaseModel):
    """Learner feedback entry persisted by the API."""

    id: str = Field(..., description="Feedback identifier")
    learnerId: str = Field(..., description="Learner identifier")
    graphId: str = Field(..., description="Graph identifier")
    sessionId: str | None = Field(default=None, description="Related tutor session id")
    stepId: str | None = Field(default=None, description="Related tutor step id")
    conceptId: str | None = Field(default=None, description="Related concept id")
    rating: int = Field(..., ge=1, le=5, description="Overall feedback rating")
    difficulty: FeedbackDifficulty = Field(..., description="Learner-perceived difficulty")
    comment: str | None = Field(default=None, description="Optional freeform comment")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    createdAt: str = Field(..., description="Creation timestamp")


class LearningProgress(BaseModel):
    """Aggregate learning progress used for tutor personalization."""

    learnerId: str = Field(..., description="Learner identifier")
    graphId: str = Field(..., description="Graph identifier")
    sessionId: str | None = Field(default=None, description="Most recent tutor session id")
    currentStepId: str | None = Field(default=None, description="Current tutor step id")
    completedStepIds: list[str] = Field(default_factory=list, description="Completed teaching steps")
    masteryByConcept: dict[str, float] = Field(default_factory=dict, description="Raw concept mastery scores")
    conceptMastery: list[ConceptMasteryState] = Field(default_factory=list, description="Structured concept mastery states")
    masteredConceptIds: list[str] = Field(default_factory=list, description="Concepts above mastery threshold")
    pendingReviewConceptIds: list[str] = Field(default_factory=list, description="Concepts below mastery threshold")
    feedbackCount: int = Field(default=0, description="Number of feedback submissions")
    averageFeedbackRating: float | None = Field(default=None, description="Average learner rating")
    eventCount: int = Field(default=0, description="Number of tracked events")
    lastEventType: LearningEventType | None = Field(default=None, description="Most recent tracked event")
    lastActivityAt: str = Field(..., description="Last activity timestamp")
    recentEvents: list[LearningEventRecord] = Field(default_factory=list, description="Recent activity timeline")
    recentFeedback: list[LearningFeedbackEntry] = Field(default_factory=list, description="Recent learner feedback")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional progress metadata")


class LearningTrackRequest(BaseModel):
    """Request model for recording a learning activity event."""

    learnerId: str = Field(..., min_length=1, description="Learner identifier")
    graphId: str = Field(..., min_length=1, description="Graph identifier")
    sessionId: str | None = Field(default=None, description="Tutor session identifier")
    stepId: str | None = Field(default=None, description="Tutor step identifier")
    conceptId: str | None = Field(default=None, description="Concept identifier")
    eventType: LearningEventType = Field(..., description="Learning event type")
    masteryDelta: float = Field(default=0.0, ge=-1.0, le=1.0, description="Optional direct mastery delta")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Optional learner confidence")
    completedStep: bool = Field(default=False, description="Mark step as completed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")


class LearningTrackResponse(BaseModel):
    """Response model for a learning track event."""

    progress: LearningProgress = Field(..., description="Updated progress snapshot")
    event: LearningEventRecord = Field(..., description="Persisted event record")


class LearningProgressResponse(BaseModel):
    """Response model for reading current learning progress."""

    progress: LearningProgress = Field(..., description="Current learning progress")


class LearningFeedbackRequest(BaseModel):
    """Request model for recording learner feedback."""

    learnerId: str = Field(..., min_length=1, description="Learner identifier")
    graphId: str = Field(..., min_length=1, description="Graph identifier")
    sessionId: str | None = Field(default=None, description="Tutor session identifier")
    stepId: str | None = Field(default=None, description="Tutor step identifier")
    conceptId: str | None = Field(default=None, description="Concept identifier")
    rating: int = Field(..., ge=1, le=5, description="Overall feedback rating")
    difficulty: FeedbackDifficulty = Field(default=FeedbackDifficulty.APPROPRIATE, description="Perceived difficulty")
    comment: str | None = Field(default=None, max_length=2000, description="Optional freeform comment")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional feedback metadata")


class LearningFeedbackResponse(BaseModel):
    """Response model for feedback submissions."""

    progress: LearningProgress = Field(..., description="Updated progress snapshot")
    feedback: LearningFeedbackEntry = Field(..., description="Persisted feedback entry")


class LearningEndpointMetrics(BaseModel):
    """Runtime counters and latency snapshot for one learning API endpoint."""

    endpoint: str = Field(..., description="Endpoint metric key")
    totalRequests: int = Field(default=0, description="Total number of requests")
    successRequests: int = Field(default=0, description="Number of successful requests")
    errorRequests: int = Field(default=0, description="Number of failed requests")
    avgLatencyMs: float | None = Field(default=None, description="Average latency in milliseconds")
    lastLatencyMs: float | None = Field(default=None, description="Most recent latency in milliseconds")
    lastStatusCode: int | None = Field(default=None, description="Most recent HTTP status code")
    lastErrorCode: str | None = Field(default=None, description="Most recent mapped error code")
    updatedAt: str | None = Field(default=None, description="Last metric update timestamp")


class LearningMetricsResponse(BaseModel):
    """Runtime learning API observability snapshot for operations troubleshooting."""

    windowStartedAt: str = Field(..., description="Metrics window start timestamp")
    generatedAt: str = Field(..., description="Snapshot generation timestamp")
    endpoints: list[LearningEndpointMetrics] = Field(
        default_factory=list,
        description="Per-endpoint counters and latency snapshots",
    )
    errorCodeMapping: dict[str, str] = Field(
        default_factory=dict,
        description="Mapped error code descriptions for operations",
    )
