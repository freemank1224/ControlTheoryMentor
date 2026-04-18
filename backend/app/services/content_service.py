"""Content generation service and persistence for P3 content artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import uuid
from typing import Any, Callable, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import close_redis_client, get_redis_client
from app.schemas.content import ContentArtifact, ContentArtifactStatus
from app.schemas.tutor import ContentArtifactType, ContentRequestResponseMode, TeachingContentRequest


class ContentStore(Protocol):
    """Storage contract for content artifacts and cache mappings."""

    def save(self, payload: dict[str, Any]) -> None:
        ...

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        ...

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        ...


def _clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


@dataclass
class InMemoryContentStore:
    """In-memory content storage for tests and fallback scenarios."""

    artifacts: dict[str, dict[str, Any]]
    cache_index: dict[str, str]

    def save(self, payload: dict[str, Any]) -> None:
        artifact_id = payload["id"]
        cache_key = payload["cacheKey"]
        self.artifacts[artifact_id] = _clone_payload(payload)
        self.cache_index[cache_key] = artifact_id

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        payload = self.artifacts.get(artifact_id)
        return _clone_payload(payload) if payload else None

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        artifact_id = self.cache_index.get(cache_key)
        if artifact_id is None:
            return None
        return self.get(artifact_id)


class RedisContentStore:
    """Redis-backed content storage with cache key lookups."""

    def __init__(
        self,
        client: Redis,
        artifact_prefix: str = "content:artifact",
        cache_prefix: str = "content:cache",
    ) -> None:
        self.client = client
        self.artifact_prefix = artifact_prefix
        self.cache_prefix = cache_prefix

    def save(self, payload: dict[str, Any]) -> None:
        artifact_id = payload["id"]
        cache_key = payload["cacheKey"]
        encoded = json.dumps(payload, ensure_ascii=False)
        pipe = self.client.pipeline()
        pipe.set(self._artifact_key(artifact_id), encoded)
        pipe.set(self._cache_key(cache_key), artifact_id)
        pipe.execute()

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        encoded = self.client.get(self._artifact_key(artifact_id))
        if not encoded:
            return None
        return json.loads(encoded)

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        artifact_id = self.client.get(self._cache_key(cache_key))
        if not artifact_id:
            return None
        return self.get(artifact_id)

    def _artifact_key(self, artifact_id: str) -> str:
        return f"{self.artifact_prefix}:{artifact_id}"

    def _cache_key(self, cache_key: str) -> str:
        return f"{self.cache_prefix}:{cache_key}"


class ContentService:
    """Generate, cache, and retrieve content artifacts."""

    def __init__(self, store: ContentStore, backend_name: str) -> None:
        self.store = store
        self.backend_name = backend_name

    def generate_content(
        self,
        request: TeachingContentRequest,
        *,
        force_regenerate: bool = False,
        interactive_mode: str | None = None,
    ) -> tuple[ContentArtifact, bool]:
        cache_key = self.build_cache_key(request)
        if not force_regenerate:
            cached = self.store.get_by_cache_key(cache_key)
            if cached is not None:
                return ContentArtifact.model_validate(cached), True

        artifact = self._build_artifact(request, cache_key=cache_key, interactive_mode=interactive_mode)
        self.store.save(artifact.model_dump(mode="json"))
        return artifact, False

    def get_artifact(self, artifact_id: str) -> ContentArtifact | None:
        payload = self.store.get(artifact_id)
        if payload is None:
            return None
        return ContentArtifact.model_validate(payload)

    @staticmethod
    def build_cache_key(request: TeachingContentRequest) -> str:
        fingerprint = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_artifact(
        self,
        request: TeachingContentRequest,
        *,
        cache_key: str,
        interactive_mode: str | None,
    ) -> ContentArtifact:
        now = datetime.now(timezone.utc).isoformat()
        artifact_id = f"content-{uuid.uuid4()}"
        requested_types = request.targetContentTypes or [ContentArtifactType.MARKDOWN]

        markdown = self._generate_markdown(request) if ContentArtifactType.MARKDOWN in requested_types else None
        mermaid = self._generate_mermaid(request) if ContentArtifactType.MERMAID in requested_types else None
        latex = self._generate_latex(request) if ContentArtifactType.LATEX in requested_types else None
        interactive = (
            self._generate_interactive_payload(request, interactive_mode)
            if ContentArtifactType.INTERACTIVE in requested_types
            else None
        )

        return ContentArtifact(
            id=artifact_id,
            status=ContentArtifactStatus.READY,
            renderHint=request.renderHint,
            targetContentTypes=requested_types,
            markdown=markdown,
            mermaid=mermaid,
            latex=latex,
            interactive=interactive,
            source=request,
            cacheKey=cache_key,
            createdAt=now,
            updatedAt=now,
            metadata={
                "generator": "template-v1",
                "responseMode": request.responseMode,
                "store": self.backend_name,
            },
        )

    @staticmethod
    def _generate_markdown(request: TeachingContentRequest) -> str:
        lines = [
            f"## {request.stepTitle}",
            "",
            request.objective,
            "",
            f"- Session Mode: {request.sessionMode.value}",
            f"- Learner Level: {request.learnerLevel}",
            f"- Stage: {request.stage.value}",
        ]
        if request.primaryConceptId:
            lines.append(f"- Primary Concept: {request.primaryConceptId}")
        if request.conceptIds:
            lines.append(f"- Related Concepts: {', '.join(request.conceptIds[:5])}")
        if request.evidencePassageIds:
            lines.append(f"- Evidence Anchors: {', '.join(request.evidencePassageIds[:3])}")

        lines.extend(
            [
                "",
                "### Learner Question",
                request.question,
            ]
        )

        if request.responseMode == ContentRequestResponseMode.INTERACTIVE:
            lines.extend(
                [
                    "",
                    "### Checkpoint",
                    "请先用 2-3 句话复述核心概念，再给出一个你会使用该概念的控制场景。",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _sanitize_mermaid_label(label: str) -> str:
        return label.replace('"', "'").replace("[", "(").replace("]", ")")[:48]

    def _generate_mermaid(self, request: TeachingContentRequest) -> str:
        concepts = request.highlightedNodeIds or request.conceptIds or ([request.primaryConceptId] if request.primaryConceptId else [])
        lines = [
            "graph TD",
            f"  Q[\"{self._sanitize_mermaid_label(request.question)}\"] --> S[\"{self._sanitize_mermaid_label(request.stepTitle)}\"]",
        ]
        for index, concept in enumerate(concepts[:5], start=1):
            lines.append(f"  S --> C{index}[\"{self._sanitize_mermaid_label(concept)}\"]")
        if request.responseMode == ContentRequestResponseMode.INTERACTIVE:
            lines.append("  S --> R[\"Learner Response\"]")
        return "\n".join(lines)

    @staticmethod
    def _generate_latex(request: TeachingContentRequest) -> str:
        if "pid" in request.question.lower() or "control" in request.question.lower():
            return r"u(t)=K_p e(t)+K_i\int_{0}^{t}e(\tau)\,d\tau+K_d\frac{de(t)}{dt}"
        return r"e(t)=r(t)-y(t)"

    @staticmethod
    def _generate_interactive_payload(request: TeachingContentRequest, interactive_mode: str | None) -> dict[str, Any]:
        return {
            "mode": interactive_mode or "guided",
            "status": "placeholder",
            "prompt": f"围绕 {request.stepTitle} 进行交互式练习。",
            "expectedResponse": "short-text",
        }


class FailoverContentService(ContentService):
    """Content service that falls back to memory when Redis is unavailable."""

    def __init__(
        self,
        primary_store: ContentStore,
        fallback_store: InMemoryContentStore,
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

    def generate_content(
        self,
        request: TeachingContentRequest,
        *,
        force_regenerate: bool = False,
        interactive_mode: str | None = None,
    ) -> tuple[ContentArtifact, bool]:
        return self._run_with_failover(
            lambda: ContentService.generate_content(
                self,
                request,
                force_regenerate=force_regenerate,
                interactive_mode=interactive_mode,
            )
        )

    def get_artifact(self, artifact_id: str) -> ContentArtifact | None:
        return self._run_with_failover(lambda: ContentService.get_artifact(self, artifact_id))

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
        except RedisError:
            self._set_fallback()
            return False
        self._set_primary()
        return True

    def _set_primary(self) -> None:
        self.store = self.primary_store
        self.backend_name = self.primary_backend_name

    def _set_fallback(self) -> None:
        self.store = self.fallback_store
        self.backend_name = self.fallback_backend_name


_content_service: ContentService | None = None
_fallback_store = InMemoryContentStore(artifacts={}, cache_index={})


def get_content_service() -> ContentService:
    """Return the default content service with Redis-first failover behavior."""

    global _content_service
    if _content_service is not None:
        return _content_service

    client = get_redis_client()
    service = FailoverContentService(
        primary_store=RedisContentStore(client),
        fallback_store=_fallback_store,
        healthcheck=client.ping,
    )
    try:
        client.ping()
        _content_service = service
    except RedisError:
        service._set_fallback()
        _content_service = service
    return _content_service


def reset_content_service() -> None:
    """Reset cached content service and fallback storage."""

    global _content_service
    _content_service = None
    _fallback_store.artifacts.clear()
    _fallback_store.cache_index.clear()
    close_redis_client()
