"""Learning loop API routes for tracking progress and feedback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.exceptions import RedisError

from app.schemas.learning import (
    LearningEndpointMetrics,
    LearningFeedbackRequest,
    LearningFeedbackResponse,
    LearningMetricsResponse,
    LearningProgressResponse,
    LearningTrackRequest,
    LearningTrackResponse,
)
from app.services.learning_service import LearningService, get_learning_service

router = APIRouter(prefix="/learning", tags=["Learning"])
logger = logging.getLogger(__name__)

ERROR_CODE_MAPPING: dict[str, str] = {
    "LEARNING_INVALID_REQUEST": "Request validation failed (FastAPI validation layer, HTTP 422).",
    "LEARNING_STORE_UNAVAILABLE": "Learning persistence store is temporarily unavailable (HTTP 503).",
    "LEARNING_TRACK_FAILED": "Unexpected failure while writing learning event (HTTP 500).",
    "LEARNING_PROGRESS_READ_FAILED": "Unexpected failure while reading learning progress (HTTP 500).",
    "LEARNING_FEEDBACK_FAILED": "Unexpected failure while submitting learning feedback (HTTP 500).",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _EndpointRuntimeMetric:
    endpoint: str
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float | None = None
    last_status_code: int | None = None
    last_error_code: str | None = None
    updated_at: str | None = None

    def record(self, status_code: int, latency_ms: float, error_code: str | None) -> None:
        self.total_requests += 1
        if status_code < 400:
            self.success_requests += 1
        else:
            self.error_requests += 1

        self.total_latency_ms += latency_ms
        self.last_latency_ms = round(latency_ms, 2)
        self.last_status_code = status_code
        self.last_error_code = error_code
        self.updated_at = _utc_now_iso()

    def to_model(self) -> LearningEndpointMetrics:
        avg_latency = None
        if self.total_requests > 0:
            avg_latency = round(self.total_latency_ms / self.total_requests, 2)
        return LearningEndpointMetrics(
            endpoint=self.endpoint,
            totalRequests=self.total_requests,
            successRequests=self.success_requests,
            errorRequests=self.error_requests,
            avgLatencyMs=avg_latency,
            lastLatencyMs=self.last_latency_ms,
            lastStatusCode=self.last_status_code,
            lastErrorCode=self.last_error_code,
            updatedAt=self.updated_at,
        )


class _LearningRuntimeMetrics:
    def __init__(self) -> None:
        self.window_started_at = _utc_now_iso()
        self._endpoints: dict[str, _EndpointRuntimeMetric] = {
            "track": _EndpointRuntimeMetric(endpoint="track"),
            "progress": _EndpointRuntimeMetric(endpoint="progress"),
            "feedback": _EndpointRuntimeMetric(endpoint="feedback"),
        }

    def record(self, endpoint: str, status_code: int, latency_ms: float, error_code: str | None = None) -> None:
        metric = self._endpoints.setdefault(endpoint, _EndpointRuntimeMetric(endpoint=endpoint))
        metric.record(status_code=status_code, latency_ms=latency_ms, error_code=error_code)

    def snapshot(self) -> LearningMetricsResponse:
        return LearningMetricsResponse(
            windowStartedAt=self.window_started_at,
            generatedAt=_utc_now_iso(),
            endpoints=[metric.to_model() for metric in self._endpoints.values()],
            errorCodeMapping=ERROR_CODE_MAPPING,
        )


learning_runtime_metrics = _LearningRuntimeMetrics()


def _extract_error_code(detail: object, fallback: str) -> str:
    if isinstance(detail, dict):
        code = detail.get("code")
        if isinstance(code, str) and code:
            return code
    return fallback


@router.post("/track", response_model=LearningTrackResponse)
async def track_learning_event(
    request: LearningTrackRequest,
    learning_service: LearningService = Depends(get_learning_service),
):
    """Record a learner event and return updated progress."""

    status_code = 200
    error_code: str | None = None
    started_at = perf_counter()
    try:
        progress, event = learning_service.track_event(request)
        return LearningTrackResponse(progress=progress, event=event)
    except HTTPException as exc:
        status_code = exc.status_code
        error_code = _extract_error_code(exc.detail, "LEARNING_TRACK_FAILED")
        raise
    except RedisError as exc:
        status_code = 503
        error_code = "LEARNING_STORE_UNAVAILABLE"
        logger.exception("Learning track failed due to persistence outage")
        raise HTTPException(
            status_code=503,
            detail={
                "code": error_code,
                "message": "Learning persistence is temporarily unavailable.",
                "cause": str(exc),
            },
        ) from exc
    except Exception as exc:
        status_code = 500
        error_code = "LEARNING_TRACK_FAILED"
        logger.exception("Learning track failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_code,
                "message": "Failed to track learning event.",
            },
        ) from exc
    finally:
        learning_runtime_metrics.record(
            endpoint="track",
            status_code=status_code,
            latency_ms=(perf_counter() - started_at) * 1000,
            error_code=error_code,
        )


@router.get("/progress", response_model=LearningProgressResponse)
async def get_learning_progress(
    learnerId: str = Query(..., min_length=1),
    graphId: str = Query(..., min_length=1),
    learning_service: LearningService = Depends(get_learning_service),
):
    """Get latest learner progress snapshot for one graph."""

    status_code = 200
    error_code: str | None = None
    started_at = perf_counter()
    try:
        progress = learning_service.get_progress(learnerId, graphId)
        return LearningProgressResponse(progress=progress)
    except HTTPException as exc:
        status_code = exc.status_code
        error_code = _extract_error_code(exc.detail, "LEARNING_PROGRESS_READ_FAILED")
        raise
    except RedisError as exc:
        status_code = 503
        error_code = "LEARNING_STORE_UNAVAILABLE"
        logger.exception("Learning progress read failed due to persistence outage")
        raise HTTPException(
            status_code=503,
            detail={
                "code": error_code,
                "message": "Learning persistence is temporarily unavailable.",
                "cause": str(exc),
            },
        ) from exc
    except Exception as exc:
        status_code = 500
        error_code = "LEARNING_PROGRESS_READ_FAILED"
        logger.exception("Learning progress read failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_code,
                "message": "Failed to read learning progress.",
            },
        ) from exc
    finally:
        learning_runtime_metrics.record(
            endpoint="progress",
            status_code=status_code,
            latency_ms=(perf_counter() - started_at) * 1000,
            error_code=error_code,
        )


@router.post("/feedback", response_model=LearningFeedbackResponse)
async def submit_learning_feedback(
    request: LearningFeedbackRequest,
    learning_service: LearningService = Depends(get_learning_service),
):
    """Submit learner feedback and return updated progress."""

    status_code = 200
    error_code: str | None = None
    started_at = perf_counter()
    try:
        progress, feedback = learning_service.submit_feedback(request)
        return LearningFeedbackResponse(progress=progress, feedback=feedback)
    except HTTPException as exc:
        status_code = exc.status_code
        error_code = _extract_error_code(exc.detail, "LEARNING_FEEDBACK_FAILED")
        raise
    except RedisError as exc:
        status_code = 503
        error_code = "LEARNING_STORE_UNAVAILABLE"
        logger.exception("Learning feedback failed due to persistence outage")
        raise HTTPException(
            status_code=503,
            detail={
                "code": error_code,
                "message": "Learning persistence is temporarily unavailable.",
                "cause": str(exc),
            },
        ) from exc
    except Exception as exc:
        status_code = 500
        error_code = "LEARNING_FEEDBACK_FAILED"
        logger.exception("Learning feedback failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail={
                "code": error_code,
                "message": "Failed to submit learning feedback.",
            },
        ) from exc
    finally:
        learning_runtime_metrics.record(
            endpoint="feedback",
            status_code=status_code,
            latency_ms=(perf_counter() - started_at) * 1000,
            error_code=error_code,
        )


@router.get("/metrics", response_model=LearningMetricsResponse)
async def get_learning_runtime_metrics():
    """Return baseline runtime metrics and error code mapping for learning API operations."""

    return learning_runtime_metrics.snapshot()
