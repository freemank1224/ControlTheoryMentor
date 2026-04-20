"""Unit tests for ContentReviewService."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.content import ContentArtifact, ContentArtifactStatus, ContentGenerationParams
from app.schemas.review import ConflictSeverity, ContentReviewResult
from app.schemas.tutor import (
    ContentArtifactType,
    ContentRequestResponseMode,
    TeachingContentRequest,
)
from app.services.content_service import ContentService, InMemoryContentStore
from app.services.graph_service import GraphService, GraphNotFoundError, GraphSnapshot
from app.services.review_service import (
    PASS_THRESHOLD,
    ContentReviewService,
    reset_review_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> TeachingContentRequest:
    defaults = dict(
        stage="concept",
        stepId="step-1",
        stepTitle="PID 控制简介",
        objective="解释 PID 控制器如何消除稳态误差",
        question="How does PID reduce steady-state error?",
        graphId="graph-test-123",
        sessionMode="interactive",   # TutorMode accepts lowercase via str enum
        learnerLevel="intermediate",
        responseMode="interactive",  # ContentRequestResponseMode
        primaryConceptId="concept-pid",
        conceptIds=["concept-pid", "concept-feedback"],
        evidenceExcerpts=["Integral action removes steady-state error by accumulating the error over time."],
        targetContentTypes=["markdown", "mermaid", "latex"],
        renderHint="markdown",
    )
    defaults.update(overrides)
    return TeachingContentRequest(**defaults)


def _make_artifact(markdown: str = "## PID\n积分作用消除稳态误差。") -> ContentArtifact:
    request = _make_request()
    return ContentArtifact(
        id="content-test-001",
        status=ContentArtifactStatus.READY,
        renderHint=ContentArtifactType.MARKDOWN,
        targetContentTypes=[ContentArtifactType.MARKDOWN, ContentArtifactType.MERMAID, ContentArtifactType.LATEX],
        markdown=markdown,
        mermaid="graph TD\n  Q --> S",
        latex=r"u(t)=K_p e(t)+K_i\int e\,dt+K_d\frac{de}{dt}",
        source=request,
        cacheKey="test-cache-key",
        createdAt="2026-01-01T00:00:00+00:00",
        updatedAt="2026-01-01T00:00:00+00:00",
        metadata={
            "contentSource": "llm",
            "llmAttempted": True,
            "generator": "llm-v1",
        },
    )


def _make_graph_service_mock(has_graph: bool = True) -> MagicMock:
    mock = MagicMock(spec=GraphService)
    if has_graph:
        snapshot = MagicMock(spec=GraphSnapshot)
        snapshot.nodes_by_id = {
            "n1": {"id": "n1", "label": "PID Controller", "properties": {"description": "A control loop mechanism."}},
            "n2": {"id": "n2", "label": "Integral Action", "properties": {"description": "Eliminates steady-state error."}},
        }
        snapshot.source_chunks = [
            {"text": "The integral term accumulates error and drives steady-state error to zero."},
            {"text": "PID controllers are widely used in industrial control systems."},
        ]
        mock.get_graph_snapshot.return_value = snapshot
    else:
        mock.get_graph_snapshot.side_effect = GraphNotFoundError("graph-test-123 not found")
    return mock


# ---------------------------------------------------------------------------
# Rule-based fallback tests (no LLM)
# ---------------------------------------------------------------------------


class TestRuleBasedReview:
    def test_llm_content_grounded_passes(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock(has_graph=False))
        artifact = _make_artifact()
        result = svc._rule_based_review(artifact, _make_request(), "graph-test-123")

        assert result.score >= PASS_THRESHOLD
        assert result.passed is True
        assert result.recommendation == "pass"

    def test_template_content_ungrounded_fails(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock(has_graph=False))
        artifact = _make_artifact()
        # Simulate template-only, ungrounded artifact
        artifact = artifact.model_copy(update={
            "metadata": {
                "contentSource": "template",
                "llmAttempted": False,
                "generator": "template-v2",
            }
        })
        request = _make_request(primaryConceptId=None, conceptIds=[], evidenceExcerpts=[])
        result = svc._rule_based_review(artifact, request, "graph-test-123")

        assert result.score < PASS_THRESHOLD
        assert result.passed is False
        assert result.recommendation == "revise"

    def test_llm_fallback_penalises_score(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock(has_graph=False))
        artifact = _make_artifact()
        artifact = artifact.model_copy(update={
            "metadata": {
                "contentSource": "template",
                "llmAttempted": True,
                "generator": "template-v2",
            }
        })
        result = svc._rule_based_review(artifact, _make_request(), "graph-test-123")
        # The penalised template score should be less than the unpenalised template score
        assert result.score < 78


# ---------------------------------------------------------------------------
# Review result schema
# ---------------------------------------------------------------------------


class TestContentReviewResult:
    def test_passed_flag_consistent_with_score(self):
        result = ContentReviewResult(
            artifactId="a1",
            graphId="g1",
            score=90,
            passed=True,
            recommendation="pass",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        assert result.passed is True
        assert result.recommendation == "pass"

    def test_failed_flag_for_low_score(self):
        result = ContentReviewResult(
            artifactId="a1",
            graphId="g1",
            score=70,
            passed=False,
            recommendation="revise",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        assert result.passed is False
        assert result.recommendation == "revise"

    def test_serialises_to_json(self):
        result = ContentReviewResult(
            artifactId="a1",
            graphId="g1",
            score=85,
            passed=True,
            recommendation="pass",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        data = result.model_dump(mode="json")
        assert data["score"] == 85
        assert data["passed"] is True


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


class TestParseReviewJson:
    def test_parses_clean_json(self):
        raw = json.dumps({
            "score": 88,
            "conflicts": [],
            "consistencies": [{"field": "markdown", "description": "OK"}],
            "qualityNotes": "Good quality",
        })
        result = ContentReviewService._parse_review_json(raw)
        assert result is not None
        assert result["score"] == 88

    def test_parses_json_with_markdown_fence(self):
        raw = "```json\n{\"score\": 75, \"conflicts\": [], \"consistencies\": [], \"qualityNotes\": \"meh\"}\n```"
        result = ContentReviewService._parse_review_json(raw)
        assert result is not None
        assert result["score"] == 75

    def test_returns_none_for_invalid_json(self):
        result = ContentReviewService._parse_review_json("not json at all")
        assert result is None

    def test_extracts_json_embedded_in_text(self):
        raw = 'Here is the review: {"score": 90, "conflicts": [], "consistencies": [], "qualityNotes": "great"} done.'
        result = ContentReviewService._parse_review_json(raw)
        assert result is not None
        assert result["score"] == 90


# ---------------------------------------------------------------------------
# LLM review path (mocked)
# ---------------------------------------------------------------------------


class TestLlmReview:
    def test_llm_review_passes_with_high_score(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        artifact = _make_artifact()
        request = _make_request()

        llm_response = json.dumps({
            "score": 92,
            "conflicts": [],
            "consistencies": [
                {"field": "markdown", "description": "与积分消除稳态误差的描述一致"}
            ],
            "qualityNotes": "内容准确，与参考资料高度一致。",
        })

        with patch.object(ContentReviewService, "_call_llm", return_value=(llm_response, {})):
            with patch.dict("os.environ", {
                "CONTENT_LLM_API_KEY": "test-key",
                "CONTENT_LLM_MODEL": "test-model",
            }):
                result = svc._llm_review(artifact, request, [], [])

        assert result is not None
        assert result.score == 92
        assert result.passed is True
        assert result.recommendation == "pass"
        assert len(result.consistencies) == 1

    def test_llm_review_revise_with_critical_conflict(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        artifact = _make_artifact()
        request = _make_request()

        llm_response = json.dumps({
            "score": 88,
            "conflicts": [
                {
                    "field": "markdown",
                    "description": "描述积分作用产生振荡，与参考资料相悖",
                    "reference": "Integral action removes steady-state error.",
                    "severity": "critical",
                }
            ],
            "consistencies": [],
            "qualityNotes": "存在严重事实错误，需修正。",
        })

        with patch.object(ContentReviewService, "_call_llm", return_value=(llm_response, {})):
            with patch.dict("os.environ", {
                "CONTENT_LLM_API_KEY": "test-key",
                "CONTENT_LLM_MODEL": "test-model",
            }):
                result = svc._llm_review(artifact, request, [], [])

        assert result is not None
        # Critical conflict forces revise even if score >= 85
        assert result.passed is False
        assert result.recommendation == "revise"
        assert result.conflicts[0].severity == ConflictSeverity.CRITICAL

    def test_llm_review_returns_none_when_no_credentials(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        artifact = _make_artifact()
        with patch.dict("os.environ", {}, clear=True):
            result = svc._llm_review(artifact, _make_request(), [], [])
        assert result is None

    def test_llm_review_falls_back_when_response_unparseable(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        artifact = _make_artifact()

        with patch.object(ContentReviewService, "_call_llm", return_value=("not json", {})):
            with patch.dict("os.environ", {
                "CONTENT_LLM_API_KEY": "test-key",
                "CONTENT_LLM_MODEL": "test-model",
            }):
                result = svc._llm_review(artifact, _make_request(), [], [])

        assert result is None  # None triggers rule-based fallback in review_artifact


# ---------------------------------------------------------------------------
# ContentService integration: review gate + retry
# ---------------------------------------------------------------------------


class TestContentServiceReviewGate:
    def _build_service_with_review(self, review_svc):
        return ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
            review_service=review_svc,
        )

    def test_review_disabled_skips_gate(self):
        svc = self._build_service_with_review(review_svc=MagicMock())
        request = _make_request()

        with patch("app.services.review_service.review_enabled", return_value=False):
            artifact, _ = svc.generate_content(request)

        # review_artifact should NOT have been called
        svc._review_service.review_artifact.assert_not_called()
        assert "review" not in artifact.metadata

    def test_review_enabled_stores_result_in_metadata(self):
        passing_result = ContentReviewResult(
            artifactId="x",
            graphId="g",
            score=90,
            passed=True,
            recommendation="pass",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        mock_review_svc = MagicMock(spec=ContentReviewService)
        mock_review_svc.review_artifact.return_value = passing_result

        svc = self._build_service_with_review(mock_review_svc)
        request = _make_request()

        with patch("app.services.review_service.review_enabled", return_value=True):
            with patch("app.services.review_service.max_retries", return_value=1):
                artifact, _ = svc.generate_content(request)

        assert "review" in artifact.metadata
        assert artifact.metadata["review"]["score"] == 90
        assert artifact.metadata["review"]["passed"] is True

    def test_review_triggers_retry_on_failure(self):
        fail_result = ContentReviewResult(
            artifactId="x",
            graphId="g",
            score=70,
            passed=False,
            recommendation="revise",
            reviewedAt="2026-01-01T00:00:00+00:00",
            qualityNotes="需要修正积分项描述。",
        )
        pass_result = ContentReviewResult(
            artifactId="x",
            graphId="g",
            score=88,
            passed=True,
            recommendation="pass",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        mock_review_svc = MagicMock(spec=ContentReviewService)
        # First call fails, second call passes
        mock_review_svc.review_artifact.side_effect = [fail_result, pass_result]

        svc = self._build_service_with_review(mock_review_svc)
        request = _make_request()

        with patch("app.services.review_service.review_enabled", return_value=True):
            with patch("app.services.review_service.max_retries", return_value=1):
                artifact, _ = svc.generate_content(request)

        # review_artifact called twice: initial + 1 retry
        assert mock_review_svc.review_artifact.call_count == 2
        assert artifact.metadata["review"]["score"] == 88

    def test_max_retries_respected(self):
        fail_result = ContentReviewResult(
            artifactId="x",
            graphId="g",
            score=60,
            passed=False,
            recommendation="revise",
            reviewedAt="2026-01-01T00:00:00+00:00",
        )
        mock_review_svc = MagicMock(spec=ContentReviewService)
        mock_review_svc.review_artifact.return_value = fail_result

        svc = self._build_service_with_review(mock_review_svc)
        request = _make_request()

        with patch("app.services.review_service.review_enabled", return_value=True):
            with patch("app.services.review_service.max_retries", return_value=2):
                artifact, _ = svc.generate_content(request)

        # 1 initial + 2 retries = 3 review calls total
        assert mock_review_svc.review_artifact.call_count == 3
        # Final review result stored even though it failed
        assert artifact.metadata["review"]["passed"] is False


# ---------------------------------------------------------------------------
# Reference loading
# ---------------------------------------------------------------------------


class TestLoadReference:
    def test_returns_nodes_and_chunks_from_snapshot(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        request = _make_request()
        nodes, chunks = svc._load_reference("graph-test-123", request)

        assert any(n.get("label") == "PID Controller" for n in nodes)
        assert any("steady-state" in c for c in chunks)

    def test_falls_back_to_evidence_excerpts_when_graph_missing(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock(has_graph=False))
        request = _make_request()
        nodes, chunks = svc._load_reference("graph-test-123", request)

        assert nodes == []
        assert "Integral action removes steady-state error" in " ".join(chunks)

    def test_empty_graph_id_uses_evidence_excerpts(self):
        svc = ContentReviewService(graph_service=_make_graph_service_mock())
        request = _make_request()
        nodes, chunks = svc._load_reference("", request)

        assert nodes == []
        assert "Integral action" in " ".join(chunks)
