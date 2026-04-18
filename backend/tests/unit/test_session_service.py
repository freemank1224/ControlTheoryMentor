"""Unit tests for session service failover and failback behavior."""

from __future__ import annotations

import pytest
from redis.exceptions import RedisError

from app.services.session_service import FailoverSessionService, InMemorySessionStore


class FlakyPrimaryStore:
    """Primary store stub that can simulate temporary Redis outages."""

    def __init__(self) -> None:
        self.store = InMemorySessionStore(data={})
        self.available = True

    def save(self, session_id: str, payload: dict):
        self._ensure_available()
        self.store.save(session_id, payload)

    def get(self, session_id: str):
        self._ensure_available()
        return self.store.get(session_id)

    def list(self, limit: int = 50):
        self._ensure_available()
        return self.store.list(limit=limit)

    def ping(self) -> None:
        self._ensure_available()

    def go_down(self) -> None:
        self.available = False

    def recover(self) -> None:
        self.available = True

    def _ensure_available(self) -> None:
        if not self.available:
            raise RedisError("redis temporarily unavailable")


def make_session_payload(session_id: str = "session-1", updated_at: str = "2026-04-18T10:00:00+00:00") -> dict:
    return {
        "id": session_id,
        "question": "Explain PID controllers",
        "pdfId": "graph-task-123",
        "mode": "interactive",
        "context": {"learning_level": "beginner"},
        "analysis": {"highlightedNodeIds": ["concept-pid"]},
        "topics": ["PID Controller"],
        "plan": {"summary": "plan", "goals": [], "steps": []},
        "messages": [],
        "currentStepIndex": 0,
        "status": "ready",
        "awaitingResponse": False,
        "createdAt": updated_at,
        "updatedAt": updated_at,
    }


class TestFailoverSessionService:
    """Validate runtime fallback and automatic recovery semantics."""

    def test_falls_back_to_memory_when_primary_save_fails(self):
        primary = FlakyPrimaryStore()
        fallback = InMemorySessionStore(data={})
        service = FailoverSessionService(primary, fallback, healthcheck=primary.ping, primary_backend_name="redis-test")

        payload = make_session_payload()
        service.save_session(payload)
        assert service.backend_name == "redis-test"

        primary.go_down()
        payload["currentStepIndex"] = 1
        payload["updatedAt"] = "2026-04-18T10:05:00+00:00"
        service.save_session(payload)

        assert service.backend_name == "memory-fallback"
        assert fallback.get("session-1")["currentStepIndex"] == 1

    def test_restores_primary_and_syncs_fallback_sessions_after_recovery(self):
        primary = FlakyPrimaryStore()
        fallback = InMemorySessionStore(data={})
        service = FailoverSessionService(primary, fallback, healthcheck=primary.ping, primary_backend_name="redis-test")

        payload = make_session_payload()
        service.save_session(payload)

        primary.go_down()
        payload["currentStepIndex"] = 2
        payload["updatedAt"] = "2026-04-18T10:06:00+00:00"
        service.save_session(payload)
        assert service.backend_name == "memory-fallback"

        primary.recover()
        recovered = service.get_session("session-1")

        assert service.backend_name == "redis-test"
        assert recovered is not None
        assert recovered["currentStepIndex"] == 2
        assert primary.get("session-1")["currentStepIndex"] == 2

    def test_starting_in_fallback_can_fail_back_without_recreating_service(self):
        primary = FlakyPrimaryStore()
        primary.go_down()
        fallback = InMemorySessionStore(data={})
        service = FailoverSessionService(primary, fallback, healthcheck=primary.ping, primary_backend_name="redis-test")
        service.start_with_fallback()

        payload = make_session_payload(session_id="session-2")
        service.save_session(payload)
        assert service.backend_name == "memory-fallback"

        primary.recover()
        sessions = service.list_sessions(limit=10)

        assert service.backend_name == "redis-test"
        assert len(sessions) == 1
        assert primary.get("session-2") is not None