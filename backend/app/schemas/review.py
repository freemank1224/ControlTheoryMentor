"""Schemas for the content review agent — quality gating for generated artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConflictSeverity(str, Enum):
    """How seriously the generated content diverges from reference material."""

    CRITICAL = "critical"  # Factually contradicts reference material
    WARNING = "warning"    # Potentially inaccurate or misleading statement
    NOTE = "note"          # Minor deviation or imprecise phrasing


class ConflictItem(BaseModel):
    """A single detected conflict between generated content and reference material."""

    field: str = Field(..., description="Content modality where the conflict was found (e.g. 'markdown', 'latex')")
    description: str = Field(..., description="Human-readable description of the conflict")
    reference: str = Field(..., description="Excerpt from reference material that contradicts the content")
    severity: ConflictSeverity = Field(default=ConflictSeverity.WARNING, description="Severity of the conflict")


class ConsistencyItem(BaseModel):
    """A single confirmed alignment between generated content and reference material."""

    field: str = Field(..., description="Content modality where the consistency was confirmed")
    description: str = Field(..., description="Human-readable description of what matches the reference")


class ContentReviewResult(BaseModel):
    """Complete quality review result for a generated content artifact."""

    artifactId: str = Field(..., description="ID of the reviewed content artifact")
    graphId: str = Field(default="", description="Graph ID used as the primary reference source")
    score: int = Field(..., ge=0, le=100, description="Quality score 0–100 (≥85 passes)")
    passed: bool = Field(..., description="True when score ≥ 85 and no critical conflicts exist")
    recommendation: str = Field(..., description="'pass' or 'revise'")
    conflicts: List[ConflictItem] = Field(default_factory=list, description="Content items conflicting with reference")
    consistencies: List[ConsistencyItem] = Field(default_factory=list, description="Content items consistent with reference")
    qualityNotes: str = Field(default="", description="Overall quality assessment and revision guidance")
    reviewedAt: str = Field(..., description="ISO-8601 review timestamp")
    reviewMeta: Dict[str, Any] = Field(default_factory=dict, description="Review process metadata (LLM provider, attempt, etc.)")


class ContentReviewRequest(BaseModel):
    """Request body for triggering a manual review of an existing artifact."""

    artifactId: str = Field(..., description="ID of the artifact to review")
    graphId: Optional[str] = Field(default=None, description="Override graph ID for reference lookup")
    forceReview: bool = Field(default=False, description="Re-run review even if a result is already cached")


class ContentReviewResponse(BaseModel):
    """Response returned from the review endpoint."""

    result: ContentReviewResult = Field(..., description="The review result")
    cached: bool = Field(default=False, description="True when the returned result was read from cache")
