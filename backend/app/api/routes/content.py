"""Content API routes for artifact generation and retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.content import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    ContentInteractiveRequest,
    ContentTypedPayloadResponse,
)
from app.schemas.tutor import ContentArtifactType
from app.services.content_service import ContentService, get_content_service

router = APIRouter(prefix="/content", tags=["Content"])


@router.post("/generate", response_model=ContentGenerateResponse)
async def generate_content_artifact(
    request: ContentGenerateRequest,
    content_service: ContentService = Depends(get_content_service),
):
    """Generate (or fetch cached) content artifact for a tutor step request."""

    artifact, cache_hit = content_service.generate_content(
        request.contentRequest,
        force_regenerate=request.forceRegenerate,
    )
    return ContentGenerateResponse(artifact=artifact, cacheHit=cache_hit)


@router.post("/interactive", response_model=ContentGenerateResponse)
async def generate_interactive_content_artifact(
    request: ContentInteractiveRequest,
    content_service: ContentService = Depends(get_content_service),
):
    """Generate an interactive placeholder artifact for P3 protocol coverage."""

    content_request = request.contentRequest.model_copy(deep=True)
    if ContentArtifactType.INTERACTIVE not in content_request.targetContentTypes:
        content_request.targetContentTypes = [*content_request.targetContentTypes, ContentArtifactType.INTERACTIVE]

    artifact, cache_hit = content_service.generate_content(
        content_request,
        interactive_mode=request.interactionMode,
    )
    return ContentGenerateResponse(artifact=artifact, cacheHit=cache_hit)


@router.get("/{artifact_id}", response_model=ContentGenerateResponse)
async def get_content_artifact(
    artifact_id: str,
    content_service: ContentService = Depends(get_content_service),
):
    """Get a previously generated content artifact by id."""

    artifact = content_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Content artifact not found")
    return ContentGenerateResponse(artifact=artifact, cacheHit=True)


@router.get("/{artifact_id}/mermaid", response_model=ContentTypedPayloadResponse)
async def get_content_mermaid(
    artifact_id: str,
    content_service: ContentService = Depends(get_content_service),
):
    """Get Mermaid payload for a content artifact."""

    artifact = content_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Content artifact not found")
    if not artifact.mermaid:
        raise HTTPException(status_code=404, detail="Mermaid payload not available for this artifact")

    return ContentTypedPayloadResponse(
        id=artifact.id,
        type=ContentArtifactType.MERMAID,
        status=artifact.status,
        content=artifact.mermaid,
        metadata={
            "renderHint": artifact.renderHint,
            "store": artifact.metadata.get("store"),
        },
    )


@router.get("/{artifact_id}/latex", response_model=ContentTypedPayloadResponse)
async def get_content_latex(
    artifact_id: str,
    content_service: ContentService = Depends(get_content_service),
):
    """Get LaTeX payload for a content artifact."""

    artifact = content_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Content artifact not found")
    if not artifact.latex:
        raise HTTPException(status_code=404, detail="LaTeX payload not available for this artifact")

    return ContentTypedPayloadResponse(
        id=artifact.id,
        type=ContentArtifactType.LATEX,
        status=artifact.status,
        content=artifact.latex,
        metadata={
            "renderHint": artifact.renderHint,
            "store": artifact.metadata.get("store"),
        },
    )
