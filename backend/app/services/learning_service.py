"""Learning tracking service with Redis-first persistence and memory failover."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Callable, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import close_redis_client, get_redis_client
from app.schemas.learning import (
    FeedbackDifficulty,
    LearningEventRecord,
    LearningEventType,
    LearningFeedbackEntry,
    LearningFeedbackRequest,
    LearningProgress,
    LearningTrackRequest,
    MasteryLevel,
)


class LearningStore(Protocol):
    """Storage contract for learner progress snapshots."""

    def save(self, progress_key: str, payload: dict[str, Any]) -> None:
        ...

    def get(self, progress_key: str) -> dict[str, Any] | None:
        ...


def _clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


@dataclass
class InMemoryLearningStore:
    """In-memory store for tests and fallback runtime mode."""

    data: dict[str, dict[str, Any]]

    def save(self, progress_key: str, payload: dict[str, Any]) -> None:
        self.data[progress_key] = _clone_payload(payload)

    def get(self, progress_key: str) -> dict[str, Any] | None:
        payload = self.data.get(progress_key)
        if payload is None:
            return None
        return _clone_payload(payload)


class RedisLearningStore:
    """Redis-backed store for learner progress snapshots."""

    def __init__(self, client: Redis, prefix: str = "learning:progress") -> None:
        self.client = client
        self.prefix = prefix

    def save(self, progress_key: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        self.client.set(self._key(progress_key), encoded)

    def get(self, progress_key: str) -> dict[str, Any] | None:
        encoded = self.client.get(self._key(progress_key))
        if not encoded:
            return None
        return json.loads(encoded)

    def _key(self, progress_key: str) -> str:
        return f"{self.prefix}:{progress_key}"


class LearningService:
    """High-level learning loop service for tracking and personalization."""

    def __init__(self, store: LearningStore, backend_name: str) -> None:
        self.store = store
        self.backend_name = backend_name

    def get_progress(self, learner_id: str, graph_id: str) -> LearningProgress:
        payload = self.store.get(self._progress_key(learner_id, graph_id))
        if payload is None:
            payload = self._new_progress_payload(learner_id, graph_id)
        return self._to_progress_model(payload)

    def track_event(self, request: LearningTrackRequest) -> tuple[LearningProgress, LearningEventRecord]:
        key = self._progress_key(request.learnerId, request.graphId)
        payload = self.store.get(key) or self._new_progress_payload(request.learnerId, request.graphId)

        timestamp = self._utc_now_iso()
        if request.sessionId:
            payload["sessionId"] = request.sessionId
        if request.stepId and request.eventType in {LearningEventType.STEP_STARTED, LearningEventType.STEP_RESPONSE}:
            payload["currentStepId"] = request.stepId

        if request.stepId and (
            request.completedStep
            or request.eventType in {LearningEventType.STEP_COMPLETED, LearningEventType.SESSION_COMPLETED}
        ):
            completed = set(payload.get("completedStepIds", []))
            completed.add(request.stepId)
            payload["completedStepIds"] = sorted(completed)

        applied_delta = self._resolve_mastery_delta(request)
        if request.conceptId:
            mastery = payload.setdefault("masteryByConcept", {})
            current = float(mastery.get(request.conceptId, 0.35))
            mastery[request.conceptId] = self._clamp(current + applied_delta, 0.0, 1.0)

        event = LearningEventRecord(
            id=f"evt-{uuid.uuid4()}",
            eventType=request.eventType,
            timestamp=timestamp,
            sessionId=request.sessionId,
            stepId=request.stepId,
            conceptId=request.conceptId,
            confidence=request.confidence,
            masteryDelta=round(applied_delta, 4),
            metadata=request.metadata,
        )

        recent_events = payload.get("recentEvents", [])
        recent_events.append(event.model_dump(mode="json"))
        payload["recentEvents"] = recent_events[-20:]
        payload["eventCount"] = int(payload.get("eventCount", 0)) + 1
        payload["lastEventType"] = request.eventType.value
        payload["lastActivityAt"] = timestamp

        self.store.save(key, payload)
        return self._to_progress_model(payload), event

    def submit_feedback(self, request: LearningFeedbackRequest) -> tuple[LearningProgress, LearningFeedbackEntry]:
        key = self._progress_key(request.learnerId, request.graphId)
        payload = self.store.get(key) or self._new_progress_payload(request.learnerId, request.graphId)
        timestamp = self._utc_now_iso()

        feedback = LearningFeedbackEntry(
            id=f"feedback-{uuid.uuid4()}",
            learnerId=request.learnerId,
            graphId=request.graphId,
            sessionId=request.sessionId,
            stepId=request.stepId,
            conceptId=request.conceptId,
            rating=request.rating,
            difficulty=request.difficulty,
            comment=request.comment,
            metadata=request.metadata,
            createdAt=timestamp,
        )

        feedback_items = payload.get("recentFeedback", [])
        feedback_items.append(feedback.model_dump(mode="json"))
        payload["recentFeedback"] = feedback_items[-20:]

        payload["feedbackCount"] = int(payload.get("feedbackCount", 0)) + 1
        payload["feedbackTotal"] = float(payload.get("feedbackTotal", 0.0)) + float(request.rating)

        payload["averageFeedbackRating"] = round(
            payload["feedbackTotal"] / max(payload["feedbackCount"], 1),
            2,
        )

        if request.sessionId:
            payload["sessionId"] = request.sessionId
        if request.stepId:
            payload["currentStepId"] = request.stepId
        payload["lastActivityAt"] = timestamp

        if request.conceptId:
            mastery = payload.setdefault("masteryByConcept", {})
            current = float(mastery.get(request.conceptId, 0.35))
            mastery_adjustment = self._feedback_mastery_adjustment(request.difficulty)
            mastery[request.conceptId] = self._clamp(current + mastery_adjustment, 0.0, 1.0)

        payload["metadata"] = {
            **payload.get("metadata", {}),
            "lastDifficulty": request.difficulty.value,
        }

        self.store.save(key, payload)
        return self._to_progress_model(payload), feedback

    @staticmethod
    def _feedback_mastery_adjustment(difficulty: FeedbackDifficulty) -> float:
        if difficulty == FeedbackDifficulty.TOO_HARD:
            return -0.06
        if difficulty == FeedbackDifficulty.TOO_EASY:
            return 0.03
        return 0.01

    @staticmethod
    def _resolve_mastery_delta(request: LearningTrackRequest) -> float:
        if abs(request.masteryDelta) > 0:
            return request.masteryDelta
        if request.confidence is None:
            return 0.0
        centered = request.confidence - 0.5
        return centered * 0.2

    def _to_progress_model(self, payload: dict[str, Any]) -> LearningProgress:
        mastery_scores = {
            concept_id: self._clamp(float(score), 0.0, 1.0)
            for concept_id, score in payload.get("masteryByConcept", {}).items()
        }
        concept_states = [
            {
                "conceptId": concept_id,
                "score": round(score, 4),
                "level": self._level_for(score).value,
                "updatedAt": payload.get("lastActivityAt") or self._utc_now_iso(),
            }
            for concept_id, score in mastery_scores.items()
        ]
        concept_states.sort(key=lambda item: item["score"]) 

        mastered = [state["conceptId"] for state in concept_states if state["score"] >= 0.75]
        pending_review = [state["conceptId"] for state in concept_states if state["score"] < 0.55]

        return LearningProgress.model_validate(
            {
                "learnerId": payload["learnerId"],
                "graphId": payload["graphId"],
                "sessionId": payload.get("sessionId"),
                "currentStepId": payload.get("currentStepId"),
                "completedStepIds": payload.get("completedStepIds", []),
                "masteryByConcept": mastery_scores,
                "conceptMastery": concept_states,
                "masteredConceptIds": mastered,
                "pendingReviewConceptIds": pending_review,
                "feedbackCount": int(payload.get("feedbackCount", 0)),
                "averageFeedbackRating": payload.get("averageFeedbackRating"),
                "eventCount": int(payload.get("eventCount", 0)),
                "lastEventType": payload.get("lastEventType"),
                "lastActivityAt": payload.get("lastActivityAt") or self._utc_now_iso(),
                "recentEvents": payload.get("recentEvents", []),
                "recentFeedback": payload.get("recentFeedback", []),
                "metadata": {
                    **payload.get("metadata", {}),
                    "store": self.backend_name,
                },
            }
        )

    def _new_progress_payload(self, learner_id: str, graph_id: str) -> dict[str, Any]:
        now = self._utc_now_iso()
        return {
            "learnerId": learner_id,
            "graphId": graph_id,
            "sessionId": None,
            "currentStepId": None,
            "completedStepIds": [],
            "masteryByConcept": {},
            "eventCount": 0,
            "feedbackCount": 0,
            "feedbackTotal": 0.0,
            "averageFeedbackRating": None,
            "lastEventType": None,
            "lastActivityAt": now,
            "recentEvents": [],
            "recentFeedback": [],
            "metadata": {},
        }

    @staticmethod
    def _progress_key(learner_id: str, graph_id: str) -> str:
        return f"{learner_id}::{graph_id}"

    @staticmethod
    def _level_for(score: float) -> MasteryLevel:
        if score >= 0.75:
            return MasteryLevel.MASTERED
        if score >= 0.55:
            return MasteryLevel.PRACTICING
        if score > 0.0:
            return MasteryLevel.DEVELOPING
        return MasteryLevel.NOT_STARTED

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class FailoverLearningService(LearningService):
    """Learning service that falls back to memory on Redis errors and auto-recovers."""

    def __init__(
        self,
        primary_store: LearningStore,
        fallback_store: InMemoryLearningStore,
        healthcheck: Callable[[], None],
        primary_backend_name: str = "redis",
        fallback_backend_name: str = "memory-fallback",
    ) -> None:
        super().__init__(store=primary_store, backend_name=primary_backend_name)
        self.primary_store = primary_store
        self.fallback_store = fallback_store
        self.healthcheck = healthcheck
        self.primary_backend_name = primary_backend_name
        self.fallback_backend_name = fallback_backend_name

    def start_with_fallback(self) -> "FailoverLearningService":
        self._set_fallback()
        return self

    def get_progress(self, learner_id: str, graph_id: str) -> LearningProgress:
        return self._run_with_failover(lambda: LearningService.get_progress(self, learner_id, graph_id))

    def track_event(self, request: LearningTrackRequest) -> tuple[LearningProgress, LearningEventRecord]:
        return self._run_with_failover(lambda: LearningService.track_event(self, request))

    def submit_feedback(self, request: LearningFeedbackRequest) -> tuple[LearningProgress, LearningFeedbackEntry]:
        return self._run_with_failover(lambda: LearningService.submit_feedback(self, request))

    def _run_with_failover(self, action: Callable[[], Any]) -> Any:
        if self.backend_name == self.fallback_backend_name and not self._try_restore_primary():
            return action()

        try:
            return action()
        except RedisError:
            self._set_fallback()
            return action()

    def _try_restore_primary(self) -> bool:
        try:
            self.healthcheck()
            self._sync_fallback_to_primary()
        except RedisError:
            self._set_fallback()
            return False
        self._set_primary()
        return True

    def _sync_fallback_to_primary(self) -> None:
        for progress_key, payload in self.fallback_store.data.items():
            self.primary_store.save(progress_key, payload)

    def _set_primary(self) -> None:
        self.store = self.primary_store
        self.backend_name = self.primary_backend_name

    def _set_fallback(self) -> None:
        self.store = self.fallback_store
        self.backend_name = self.fallback_backend_name


_learning_service: LearningService | None = None
_fallback_store = InMemoryLearningStore(data={})


def get_learning_service() -> LearningService:
    """Return the default learning service with Redis-first failover behavior."""

    global _learning_service
    if _learning_service is not None:
        return _learning_service

    client = get_redis_client()
    service = FailoverLearningService(
        primary_store=RedisLearningStore(client),
        fallback_store=_fallback_store,
        healthcheck=client.ping,
    )
    try:
        client.ping()
        _learning_service = service
    except RedisError:
        _learning_service = service.start_with_fallback()
    return _learning_service


def reset_learning_service() -> None:
    """Reset cached learning service and fallback storage."""

    global _learning_service
    _learning_service = None
    _fallback_store.data.clear()
    close_redis_client()
