"""Tutor-facing node and concept-context routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.node import (
    ConceptContextResponse,
    NodeDetail,
    NodeNeighborsResponse,
    NodeSearchResponse,
    SemanticNodeSearchRequest,
)
from app.services.graph_service import GraphNotFoundError, NodeNotFoundError
from app.services.node_service import NodeService, get_node_service

router = APIRouter(prefix="/node", tags=["Node"])


@router.get("/search", response_model=NodeSearchResponse)
async def search_nodes(
    graph_id: str = Query(..., alias="graphId"),
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    node_service: NodeService = Depends(get_node_service),
):
    """Search node labels and identifiers within a specific graph artifact."""
    try:
        return node_service.search_nodes(graph_id, q, limit=limit, mode="search")
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/fulltext", response_model=NodeSearchResponse)
async def fulltext_search_nodes(
    graph_id: str = Query(..., alias="graphId"),
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    node_service: NodeService = Depends(get_node_service),
):
    """Search across node labels, properties, and adjacent relation text."""
    try:
        return node_service.search_nodes(graph_id, q, limit=limit, mode="fulltext")
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/semantic", response_model=NodeSearchResponse)
async def semantic_search_nodes(
    request: SemanticNodeSearchRequest,
    node_service: NodeService = Depends(get_node_service),
):
    """Semantic-like node search using keyword extraction plus fulltext fallback."""
    try:
        return node_service.semantic_search(request.graphId, request.query, limit=request.limit)
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{node_id}/neighbors", response_model=NodeNeighborsResponse)
async def get_node_neighbors(
    node_id: str,
    graph_id: str = Query(..., alias="graphId"),
    limit: int = Query(25, ge=1, le=100),
    node_service: NodeService = Depends(get_node_service),
):
    """Return neighboring nodes and edges for a specific concept node."""
    try:
        return node_service.get_neighbors(graph_id, node_id, limit=limit)
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{node_id}", response_model=NodeDetail)
async def get_node_detail(
    node_id: str,
    graph_id: str = Query(..., alias="graphId"),
    node_service: NodeService = Depends(get_node_service),
):
    """Return a normalized node detail payload for tutor consumers."""
    try:
        return node_service.get_node_detail(graph_id, node_id)
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc