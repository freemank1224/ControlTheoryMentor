"""Unit tests for content generation service."""

from app.schemas.content import ContentGenerationParams
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
        evidenceExcerpts=["Integral action removes steady-state error."],
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

    def test_generate_content_covers_image_comic_animation_payloads(self):
        def fake_image_fetcher(prompt: str, timeout_ms: int):
            return "image/png", b"\x89PNG\r\n\x1a\n"

        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
            image_fetcher=fake_image_fetcher,
        )

        request = build_request(target_types=["markdown", "image", "comic", "animation"])
        artifact, cache_hit = service.generate_content(request, force_regenerate=True)

        assert cache_hit is False
        assert artifact.image is not None
        assert artifact.image["source"] == "real"
        assert artifact.image["dataUrl"].startswith("data:image/png;base64,")
        assert artifact.comic is not None
        assert artifact.animation is not None

    def test_generate_content_reports_insufficient_grounding_when_evidence_missing(self):
        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )

        request = build_request(target_types=["markdown"])
        request.evidenceExcerpts = []
        request.evidencePassageIds = []
        request.conceptIds = []
        request.primaryConceptId = None

        artifact, _ = service.generate_content(request, force_regenerate=True)

        assert artifact.markdown is not None
        assert "信息不足" in artifact.markdown
        assert artifact.metadata["llmFallbackReason"] == "insufficient_grounding"

    def test_image_generation_failure_degrades_to_fallback(self):
        def failing_fetcher(prompt: str, timeout_ms: int):
            raise TimeoutError("simulated timeout")

        service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
            image_fetcher=failing_fetcher,
        )

        request = build_request(target_types=["image"])
        request.renderHint = "image"
        artifact, _ = service.generate_content(
            request,
            force_regenerate=True,
            generation_params=ContentGenerationParams(
                style="blueprint",
                detail="high",
                pace="fast",
                attempt=3,
            ),
        )

        assert artifact.image is not None
        assert artifact.image["source"] == "fallback"
        assert artifact.image["status"] == "fallback"
        assert artifact.markdown is not None
        assert artifact.renderHint.value == "markdown"
        assert artifact.metadata["imageGeneration"]["mode"] == "fallback"
