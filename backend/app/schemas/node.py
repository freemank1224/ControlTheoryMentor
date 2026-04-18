"""Node and concept-context schemas for tutor-facing graph lookups."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeSummary(BaseModel):
    """Normalized node summary decoupled from the Cytoscape graph view format."""

    graphId: str = Field(..., description="Graph identifier containing the node")
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Human-readable node label")
    nodeType: str = Field(..., description="Tutor-facing node classification")
    fileType: str = Field(..., description="Underlying Graphify file type")
    community: int | None = Field(default=None, description="Optional graph community id")
    sourceFile: str = Field(default="", description="Source file path relative to the graph root")
    sourceLocation: str | None = Field(default=None, description="Source location such as section or equation id")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional normalized node properties")
    score: float | None = Field(default=None, description="Search score when returned from a search endpoint")
    matchReason: str | None = Field(default=None, description="Why the node matched a search query")


class NodeDetail(NodeSummary):
    """Detailed node payload returned by the node detail endpoint."""

    metadata: dict[str, Any] = Field(default_factory=dict, description="Lookup metadata for the node detail")


class NodeEdgeSummary(BaseModel):
    """Normalized edge summary for neighbor traversal responses."""

    id: str = Field(..., description="Unique edge identifier")
    relation: str = Field(..., description="Normalized relation label")
    confidence: str = Field(..., description="Graphify confidence bucket")
    confidenceScore: float | None = Field(default=None, description="Numeric confidence score if present")
    weight: float | None = Field(default=None, description="Edge weight if present")
    sourceLocation: str | None = Field(default=None, description="Source location for the relation")
    sourceFile: str = Field(default="", description="Source file path for the relation")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional edge properties")


class NodeNeighbor(BaseModel):
    """A neighboring node and the edge that connects it to the target concept."""

    direction: str = Field(..., description="Whether the edge is incoming or outgoing relative to the requested node")
    node: NodeSummary = Field(..., description="Neighbor node summary")
    edge: NodeEdgeSummary = Field(..., description="Connecting edge summary")


class NodeNeighborsResponse(BaseModel):
    """Response model for node neighbor traversal."""

    graphId: str = Field(..., description="Graph identifier")
    node: NodeSummary = Field(..., description="Requested node summary")
    items: list[NodeNeighbor] = Field(default_factory=list, description="Neighbor nodes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Traversal metadata")


class NodeSearchResponse(BaseModel):
    """Shared response shape for search, fulltext, and semantic node lookups."""

    graphId: str = Field(..., description="Graph identifier")
    query: str = Field(..., description="Original search query")
    items: list[NodeSummary] = Field(default_factory=list, description="Matching nodes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Search metadata")


class SemanticNodeSearchRequest(BaseModel):
    """Request body for semantic node search."""

    graphId: str = Field(..., description="Graph identifier to search within")
    query: str = Field(..., min_length=1, description="Learner query to map to graph concepts")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of semantic matches to return")


class SourceSection(BaseModel):
    """Source locations aggregated into the concept context package."""

    sourceFile: str = Field(..., description="Source file path relative to the graph root")
    sourceLocation: str | None = Field(default=None, description="Section or location hint from Graphify")
    sectionLabel: str = Field(..., description="Display label for the source section")


class SourcePassage(BaseModel):
    """Resolved source text passage attached to a concept context payload."""

    chunkId: str = Field(..., description="Chunk identifier inside the source chunk artifact")
    sourceFile: str = Field(..., description="Source file path relative to the graph root")
    sourceLocation: str | None = Field(default=None, description="Chunk location carried over from Graphify extraction")
    pageStart: int | None = Field(default=None, description="Starting page number when the source is a PDF")
    pageEnd: int | None = Field(default=None, description="Ending page number when the source is a PDF")
    text: str = Field(..., description="Recovered source passage text")
    relatedNodeIds: list[str] = Field(default_factory=list, description="Concept or neighbor nodes grounded by this passage")


class GraphLookupContract(BaseModel):
    """Stable tutor-facing graph lookup contract for later orchestration phases."""

    graphId: str = Field(..., description="Graph identifier")
    conceptId: str = Field(..., description="Requested concept identifier")
    sourcePriority: list[str] = Field(default_factory=list, description="Lookup priority order across backing stores")
    semanticSearchStrategy: str = Field(..., description="Semantic search strategy currently available for this graph")
    graphSource: str = Field(..., description="Primary data source used to resolve the concept")
    artifactPath: str | None = Field(default=None, description="Resolved graph artifact path when available")
    reportPath: str | None = Field(default=None, description="Resolved Graphify report path when available")
    sourceChunksPath: str | None = Field(default=None, description="Resolved source chunk artifact path when available")
    neo4jEnrichmentAvailable: bool = Field(default=False, description="Whether Neo4j enrichment is available")


class ConceptContextResponse(BaseModel):
    """Aggregated concept context package used by the tutor layer."""

    graphId: str = Field(..., description="Graph identifier")
    concept: NodeSummary = Field(..., description="Requested concept node")
    prerequisites: list[NodeSummary] = Field(default_factory=list, description="Prerequisite concepts linked to the requested concept")
    relatedNodes: list[NodeSummary] = Field(default_factory=list, description="Related concept candidates for plan expansion")
    formulas: list[NodeSummary] = Field(default_factory=list, description="Formula or equation nodes associated with the concept")
    examples: list[NodeSummary] = Field(default_factory=list, description="Example nodes associated with the concept")
    sourceSections: list[SourceSection] = Field(default_factory=list, description="Source sections grounding the concept context")
    passages: list[SourcePassage] = Field(default_factory=list, description="Recovered source passages that can be injected into tutor context")
    lookup: GraphLookupContract = Field(..., description="Stable lookup contract for tutor orchestration")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional aggregation metadata")