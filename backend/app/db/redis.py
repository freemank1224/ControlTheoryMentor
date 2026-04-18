"""Redis client helpers for tutor session persistence."""

from __future__ import annotations

from redis import Redis

from app.config import settings

_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return a shared Redis client configured from application settings."""
    global _client
    if _client is None:
        _client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def close_redis_client() -> None:
    """Close the shared Redis client if one has been created."""
    global _client
    if _client is not None:
        _client.close()
        _client = None