"""Session persistence services backed by Redis with an in-memory fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Callable, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import close_redis_client, get_redis_client


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


def _clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))


@dataclass
class InMemorySessionStore:
    """Test-friendly in-memory session storage."""

    data: dict[str, dict[str, Any]]

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        self.data[session_id] = _clone_payload(payload)

    def get(self, session_id: str) -> dict[str, Any] | None:
        payload = self.data.get(session_id)
        if payload is None:
            return None
        return _clone_payload(payload)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        items = sorted(self.data.values(), key=lambda payload: payload.get("updatedAt", ""), reverse=True)
        return [_clone_payload(item) for item in items[:limit]]

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return [(session_id, _clone_payload(payload)) for session_id, payload in self.data.items()]


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


class FailoverSessionService(SessionService):
    """Session service that falls back to memory on Redis errors and auto-recovers later."""

    def __init__(
        self,
        primary_store: SessionStore,
        fallback_store: InMemorySessionStore,
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

    def start_with_fallback(self) -> "FailoverSessionService":
        self._set_fallback()
        return self

    def save_session(self, payload: dict[str, Any]) -> None:
        session_id = payload["id"]
        self.fallback_store.save(session_id, payload)

        if self.backend_name == self.fallback_backend_name:
            self._try_restore_primary()
            return

        try:
            self.primary_store.save(session_id, payload)
        except RedisError:
            self._set_fallback()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if self.backend_name == self.fallback_backend_name and not self._try_restore_primary():
            return self.fallback_store.get(session_id)

        try:
            return self.primary_store.get(session_id)
        except RedisError:
            self._set_fallback()
            return self.fallback_store.get(session_id)

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        if self.backend_name == self.fallback_backend_name and not self._try_restore_primary():
            return self.fallback_store.list(limit=limit)

        try:
            return self.primary_store.list(limit=limit)
        except RedisError:
            self._set_fallback()
            return self.fallback_store.list(limit=limit)

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
        for session_id, payload in self.fallback_store.items():
            self.primary_store.save(session_id, payload)

    def _set_primary(self) -> None:
        self.store = self.primary_store
        self.backend_name = self.primary_backend_name

    def _set_fallback(self) -> None:
        self.store = self.fallback_store
        self.backend_name = self.fallback_backend_name


_fallback_store = InMemorySessionStore(data={})
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Return the default session service, preferring Redis when available."""
    global _session_service
    if _session_service is not None:
        return _session_service

    client = get_redis_client()
    service = FailoverSessionService(
        primary_store=RedisSessionStore(client),
        fallback_store=_fallback_store,
        healthcheck=client.ping,
    )
    try:
        client.ping()
        _session_service = service
    except RedisError:
        _session_service = service.start_with_fallback()
    return _session_service


def reset_session_service() -> None:
    """Reset the cached default session service for tests or reloads."""
    global _session_service
    _session_service = None
    _fallback_store.data.clear()
    close_redis_client()