"""Unit tests for content artifact schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.content import ContentArtifact, ContentArtifactStatus, ContentGenerateRequest


def build_content_request_payload() -> dict:
    return {
        "stage": "intro",
        "stepId": "step-1",
        "stepTitle": "建立问题背景",
        "objective": "明确学习目标",
        "question": "How does PID reduce steady-state error?",
        "graphId": "graph-task-123",
        "sessionMode": "interactive",
        "learnerLevel": "beginner",
        "responseMode": "passive",
        "primaryConceptId": "concept-pid",
        "conceptIds": ["concept-pid"],
        "highlightedNodeIds": ["concept-pid"],
        "evidencePassageIds": ["chunk-pid-1"],
        "targetContentTypes": ["markdown", "mermaid", "latex", "image", "comic", "animation"],
        "renderHint": "markdown",
    }


class TestContentSchemas:
    """Validate content request and artifact schema behavior."""

    def test_generate_request_accepts_content_contract(self):
        request = ContentGenerateRequest(
            contentRequest=build_content_request_payload(),
            generationParams={"style": "blueprint", "detail": "high", "attempt": 2},
        )

        assert request.forceRegenerate is False
        assert request.contentRequest.stepId == "step-1"
        assert request.contentRequest.targetContentTypes == ["markdown", "mermaid", "latex", "image", "comic", "animation"]
        assert request.generationParams.style == "blueprint"
        assert request.generationParams.attempt == 2

    def test_content_artifact_serializes_payloads(self):
        artifact = ContentArtifact(
            id="content-123",
            status=ContentArtifactStatus.READY,
            renderHint="markdown",
            targetContentTypes=["markdown", "mermaid", "latex", "image", "comic", "animation"],
            markdown="# Example",
            mermaid="graph TD\n  A --> B",
            latex=r"u(t)=K_p e(t)",
            image={"source": "fallback", "status": "fallback"},
            comic={"status": "ready", "panels": []},
            animation={"status": "placeholder", "keyframes": []},
            source=build_content_request_payload(),
            cacheKey="abc",
            createdAt="2026-04-18T00:00:00+00:00",
            updatedAt="2026-04-18T00:00:00+00:00",
            metadata={"store": "memory-test"},
        )

        assert artifact.status == ContentArtifactStatus.READY
        assert artifact.mermaid is not None
        assert artifact.image is not None
        assert artifact.comic is not None
        assert artifact.animation is not None
        assert artifact.source.stepId == "step-1"

    def test_content_artifact_requires_id(self):
        with pytest.raises(ValidationError):
            ContentArtifact(
                status=ContentArtifactStatus.READY,
                renderHint="markdown",
                targetContentTypes=["markdown"],
                source=build_content_request_payload(),
                cacheKey="abc",
                createdAt="2026-04-18T00:00:00+00:00",
                updatedAt="2026-04-18T00:00:00+00:00",
            )
