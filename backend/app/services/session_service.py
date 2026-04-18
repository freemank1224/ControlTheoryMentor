"""Session persistence services backed by Redis with an in-memory fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import get_redis_client


class SessionStore(Protocol):
    """Abstract session storage contract."""

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        ...

    def get(self, session_id: str) -> dict[str, Any] | None:
        ...

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        ...


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


@dataclass
class InMemorySessionStore:
    """Test-friendly in-memory session storage."""

    data: dict[str, dict[str, Any]]

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        self.data[session_id] = json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))

    def get(self, session_id: str) -> dict[str, Any] | None:
        payload = self.data.get(session_id)
        if payload is None:
            return None
        return json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        items = sorted(self.data.values(), key=lambda payload: payload.get("updatedAt", ""), reverse=True)
        return [json.loads(json.dumps(item, ensure_ascii=False, default=_json_default)) for item in items[:limit]]


class RedisSessionStore:
    """Redis-backed session storage used by the tutor orchestrator."""

    def __init__(self, client: Redis, prefix: str = "tutor:session", index_key: str = "tutor:sessions") -> None:
        self.client = client
        self.prefix = prefix
        self.index_key = index_key

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, default=_json_default)
        updated_at = payload.get("updatedAt", "")
        score = self._score_for(updated_at)
        pipe = self.client.pipeline()
        pipe.set(self._session_key(session_id), encoded)
        pipe.zadd(self.index_key, {session_id: score})
        pipe.execute()

    def get(self, session_id: str) -> dict[str, Any] | None:
        encoded = self.client.get(self._session_key(session_id))
        if not encoded:
            return None
        return json.loads(encoded)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        session_ids = self.client.zrevrange(self.index_key, 0, max(limit - 1, 0))
        if not session_ids:
            return []
        values = self.client.mget([self._session_key(session_id) for session_id in session_ids])
        return [json.loads(value) for value in values if value]

    def _session_key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    @staticmethod
    def _score_for(value: str) -> float:
        try:
            return datetime.fromisoformat(value).timestamp()
        except (TypeError, ValueError):
            return 0.0


class SessionService:
    """High-level session persistence facade for tutor orchestration."""

    def __init__(self, store: SessionStore, backend_name: str) -> None:
        self.store = store
        self.backend_name = backend_name

    def save_session(self, payload: dict[str, Any]) -> None:
        self.store.save(payload["id"], payload)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.store.get(session_id)

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list(limit=limit)


_fallback_store = InMemorySessionStore(data={})
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Return the default session service, preferring Redis when available."""
    global _session_service
    if _session_service is not None:
        return _session_service

    try:
        client = get_redis_client()
        client.ping()
        _session_service = SessionService(RedisSessionStore(client), backend_name="redis")
    except RedisError:
        _session_service = SessionService(_fallback_store, backend_name="memory-fallback")
    return _session_service