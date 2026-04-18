"""Unit tests for learning service progress tracking and failover behavior."""

from __future__ import annotations

from redis.exceptions import RedisError

from app.schemas.learning import FeedbackDifficulty, LearningEventType, LearningFeedbackRequest, LearningTrackRequest
from app.services.learning_service import (
    FailoverLearningService,
    InMemoryLearningStore,
    LearningService,
)


class FlakyPrimaryStore:
    """Primary store stub that can emulate temporary Redis outages."""

    def __init__(self) -> None:
        self.store = InMemoryLearningStore(data={})
        self.available = True

    def save(self, progress_key: str, payload: dict):
        self._ensure_available()
        self.store.save(progress_key, payload)

    def get(self, progress_key: str):
        self._ensure_available()
        return self.store.get(progress_key)

    def ping(self) -> None:
        self._ensure_available()

    def go_down(self) -> None:
        self.available = False

    def recover(self) -> None:
        self.available = True

    def _ensure_available(self) -> None:
        if not self.available:
            raise RedisError("redis temporarily unavailable")


class TestLearningService:
    """Verify progress updates, feedback aggregation, and mastery shaping."""

    def test_track_event_updates_progress_and_mastery(self):
        service = LearningService(store=InMemoryLearningStore(data={}), backend_name="memory-test")

        progress, event = service.track_event(
            LearningTrackRequest(
                learnerId="learner-1",
                graphId="graph-task-123",
                sessionId="session-1",
                stepId="step-2",
                conceptId="concept-pid",
                eventType=LearningEventType.STEP_RESPONSE,
                confidence=0.8,
                metadata={"source": "tutor"},
            )
        )

        assert event.eventType == LearningEventType.STEP_RESPONSE
        assert progress.sessionId == "session-1"
        assert progress.currentStepId == "step-2"
        assert progress.eventCount == 1
        assert progress.masteryByConcept["concept-pid"] > 0.35

    def test_feedback_updates_average_and_pending_review(self):
        service = LearningService(store=InMemoryLearningStore(data={}), backend_name="memory-test")

        service.track_event(
            LearningTrackRequest(
                learnerId="learner-1",
                graphId="graph-task-123",
                conceptId="concept-feedback",
                eventType=LearningEventType.STEP_STARTED,
                masteryDelta=0.15,
            )
        )

        progress, feedback = service.submit_feedback(
            LearningFeedbackRequest(
                learnerId="learner-1",
                graphId="graph-task-123",
                conceptId="concept-feedback",
                rating=2,
                difficulty=FeedbackDifficulty.TOO_HARD,
                comment="Need slower pacing.",
            )
        )

        assert feedback.rating == 2
        assert progress.feedbackCount == 1
        assert progress.averageFeedbackRating == 2.0
        assert "concept-feedback" in progress.pendingReviewConceptIds


class TestFailoverLearningService:
    """Validate fallback and failback behavior for learning state persistence."""

    def test_fallback_and_recovery(self):
        primary = FlakyPrimaryStore()
        fallback = InMemoryLearningStore(data={})
        service = FailoverLearningService(primary, fallback, healthcheck=primary.ping, primary_backend_name="redis-test")

        service.track_event(
            LearningTrackRequest(
                learnerId="learner-1",
                graphId="graph-task-123",
                eventType=LearningEventType.SESSION_STARTED,
            )
        )
        assert service.backend_name == "redis-test"

        primary.go_down()
        progress, _ = service.track_event(
            LearningTrackRequest(
                learnerId="learner-1",
                graphId="graph-task-123",
                eventType=LearningEventType.STEP_STARTED,
                stepId="step-1",
            )
        )
        assert service.backend_name == "memory-fallback"
        assert progress.currentStepId == "step-1"

        primary.recover()
        recovered = service.get_progress("learner-1", "graph-task-123")
        assert service.backend_name == "redis-test"
        assert recovered.currentStepId == "step-1"
