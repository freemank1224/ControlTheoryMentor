"""Learning loop API routes for tracking progress and feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.schemas.learning import (
    LearningFeedbackRequest,
    LearningFeedbackResponse,
    LearningProgressResponse,
    LearningTrackRequest,
    LearningTrackResponse,
)
from app.services.learning_service import LearningService, get_learning_service

router = APIRouter(prefix="/learning", tags=["Learning"])


@router.post("/track", response_model=LearningTrackResponse)
async def track_learning_event(
    request: LearningTrackRequest,
    learning_service: LearningService = Depends(get_learning_service),
):
    """Record a learner event and return updated progress."""

    progress, event = learning_service.track_event(request)
    return LearningTrackResponse(progress=progress, event=event)


@router.get("/progress", response_model=LearningProgressResponse)
async def get_learning_progress(
    learnerId: str = Query(..., min_length=1),
    graphId: str = Query(..., min_length=1),
    learning_service: LearningService = Depends(get_learning_service),
):
    """Get latest learner progress snapshot for one graph."""

    progress = learning_service.get_progress(learnerId, graphId)
    return LearningProgressResponse(progress=progress)


@router.post("/feedback", response_model=LearningFeedbackResponse)
async def submit_learning_feedback(
    request: LearningFeedbackRequest,
    learning_service: LearningService = Depends(get_learning_service),
):
    """Submit learner feedback and return updated progress."""

    progress, feedback = learning_service.submit_feedback(request)
    return LearningFeedbackResponse(progress=progress, feedback=feedback)
