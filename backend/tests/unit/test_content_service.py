"""Unit tests for content generation service."""

from app.schemas.tutor import TeachingContentRequest
from app.services.content_service import ContentService, InMemoryContentStore


def build_request(target_types: list[str] | None = None) -> TeachingContentRequest:
    return TeachingContentRequest(
        stage="concept",
        stepId="step-2",
        stepTitle="拆解核心概念",
        objective="将概念拆成更适合理解检查的子点。",
        question="How does PID reduce steady-state error?",
        graphId="graph-task-123",
        sessionMode="interactive",
        learnerLevel="intermediate",
        responseMode="interactive",
        primaryConceptId="concept-pid",
        conceptIds=["concept-pid", "concept-feedback"],
        highlightedNodeIds=["concept-pid"],
        evidencePassageIds=["chunk-pid-1"],
        targetContentTypes=target_types or ["markdown", "mermaid", "latex"],
        renderHint="markdown",
    )


class TestContentService:
    """Verify generation, cache reuse, and retrieval semantics."""

    def test_generate_content_produces_multitype_payloads(self):
        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )

        artifact, cache_hit = service.generate_content(build_request())

        assert cache_hit is False
        assert artifact.id.startswith("content-")
        assert artifact.markdown is not None
        assert artifact.mermaid is not None
        assert artifact.latex is not None

    def test_generate_content_reuses_cache_key(self):
        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )

        first, first_cache = service.generate_content(build_request())
        second, second_cache = service.generate_content(build_request())

        assert first_cache is False
        assert second_cache is True
        assert first.id == second.id

    def test_force_regenerate_bypasses_cache(self):
        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )

        first, _ = service.generate_content(build_request())
        second, cache_hit = service.generate_content(build_request(), force_regenerate=True)

        assert cache_hit is False
        assert first.id != second.id

    def test_get_artifact_returns_none_for_unknown_id(self):
        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )

        assert service.get_artifact("content-missing") is None
