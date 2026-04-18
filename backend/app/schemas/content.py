"""Content artifact schemas for P3 generation and rendering APIs."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.schemas.tutor import ContentArtifactType, TeachingContentRequest


class ContentArtifactStatus(str, Enum):
    """Lifecycle status for generated content artifacts."""

    READY = "ready"
    PENDING = "pending"
    FAILED = "failed"


class ContentArtifact(BaseModel):
    """Persisted content artifact that can be rendered repeatedly."""

    id: str = Field(..., description="Unique content artifact identifier")
    status: ContentArtifactStatus = Field(..., description="Generation status")
    renderHint: ContentArtifactType = Field(
        default=ContentArtifactType.MARKDOWN,
        description="Primary type the frontend should render first",
    )
    targetContentTypes: list[ContentArtifactType] = Field(
        default_factory=lambda: [ContentArtifactType.MARKDOWN],
        description="Requested content payload types",
    )
    markdown: Optional[str] = Field(default=None, description="Markdown payload when available")
    mermaid: Optional[str] = Field(default=None, description="Mermaid payload when available")
    latex: Optional[str] = Field(default=None, description="LaTeX payload when available")
    interactive: Optional[Dict[str, Any]] = Field(default=None, description="Interactive payload placeholder")
    source: TeachingContentRequest = Field(..., description="Original step-level content request")
    cacheKey: str = Field(..., description="Deterministic cache key for deduplication")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ContentGenerateRequest(BaseModel):
    """Request model for generating a content artifact."""

    contentRequest: TeachingContentRequest = Field(..., description="Step-level generation contract from tutor session")
    forceRegenerate: bool = Field(
        default=False,
        description="When true, bypass cache and generate a fresh artifact",
    )


class ContentInteractiveRequest(BaseModel):
    """Request model for the interactive content placeholder endpoint."""

    contentRequest: TeachingContentRequest = Field(..., description="Step-level generation contract from tutor session")
    interactionMode: str = Field(default="guided", min_length=1, description="Requested interactive mode placeholder")


class ContentGenerateResponse(BaseModel):
    """Response returned after content generation or cache retrieval."""

    artifact: ContentArtifact = Field(..., description="Generated or cached content artifact")
    cacheHit: bool = Field(default=False, description="Whether an existing artifact was reused")


class ContentTypedPayloadResponse(BaseModel):
    """Response for fetching a single typed payload from an artifact."""

    id: str = Field(..., description="Artifact identifier")
    type: ContentArtifactType = Field(..., description="Requested payload type")
    status: ContentArtifactStatus = Field(..., description="Artifact status")
    content: str = Field(..., description="Typed payload text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplemental metadata")
