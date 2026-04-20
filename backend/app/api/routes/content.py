"""Content API routes for artifact generation and retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.content import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    ContentInteractiveRequest,
    ContentTypedPayloadResponse,
)
from app.schemas.review import ContentReviewRequest, ContentReviewResponse
from app.schemas.tutor import ContentArtifactType
from app.services.content_service import ContentService, get_content_service
from app.services.review_service import ContentReviewService, get_review_service

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
        generation_params=request.generationParams,
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
        generation_params=request.generationParams,
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


# ---------------------------------------------------------------------------
# Review endpoints
# ---------------------------------------------------------------------------

@router.post("/{artifact_id}/review", response_model=ContentReviewResponse)
async def review_content_artifact(
    artifact_id: str,
    body: ContentReviewRequest,
    content_service: ContentService = Depends(get_content_service),
    review_service: ContentReviewService = Depends(get_review_service),
):
    """Trigger an on-demand quality review for an existing content artifact.

    The review agent compares the artifact's generated content against the
    knowledge graph nodes and source-document chunks identified by *graphId*.
    Returns a scored review result with conflict/consistency annotations.
    A score ≥ 85 results in recommendation='pass'; below that is 'revise'.
    """

    artifact = content_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Content artifact not found")

    # If a cached review is already stored in metadata and forceReview is False, return it.
    if not body.forceReview:
        cached_review = artifact.metadata.get("review")
        if cached_review:
            from app.schemas.review import ContentReviewResult
            try:
                return ContentReviewResponse(
                    result=ContentReviewResult.model_validate(cached_review),
                    cached=True,
                )
            except Exception:
                pass  # Malformed cache — fall through to re-review

    # Build a minimal TeachingContentRequest from what the artifact already knows
    source_request = artifact.source
    if body.graphId:
        source_request = source_request.model_copy(update={"graphId": body.graphId})

    result = review_service.review_artifact(artifact, source_request)

    # Persist the review result back into the artifact metadata
    updated_meta = dict(artifact.metadata)
    updated_meta["review"] = result.model_dump(mode="json")
    updated_artifact = artifact.model_copy(update={"metadata": updated_meta})
    content_service.store.save(updated_artifact.model_dump(mode="json"))

    return ContentReviewResponse(result=result, cached=False)


@router.get("/{artifact_id}/review", response_model=ContentReviewResponse)
async def get_content_review(
    artifact_id: str,
    content_service: ContentService = Depends(get_content_service),
):
    """Return the most recent review result stored on an artifact (if any).

    Returns 404 if the artifact has not been reviewed yet.  Use
    POST /{artifact_id}/review to trigger a review.
    """

    artifact = content_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Content artifact not found")

    cached_review = artifact.metadata.get("review")
    if not cached_review:
        raise HTTPException(
            status_code=404,
            detail="No review result found for this artifact. POST to /{artifact_id}/review to trigger one.",
        )

    from app.schemas.review import ContentReviewResult
    try:
        return ContentReviewResponse(
            result=ContentReviewResult.model_validate(cached_review),
            cached=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Malformed review cache: {exc}") from exc
