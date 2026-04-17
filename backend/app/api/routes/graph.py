"""
Graph API routes for knowledge graph operations
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.schemas.graph import (
    GraphNode,
    GraphEdge,
    GraphCreateRequest,
    GraphQueryRequest,
    GraphResponse,
    GraphTraversalRequest,
    NodeType,
    RelationType
)

router = APIRouter(prefix="/graph", tags=["Graph"])

# In-memory storage for demo purposes
graph_storage = {
    "nodes": {},
    "edges": {}
}


@router.post("/create")
async def create_graph_elements(request: GraphCreateRequest):
    """
    Create graph nodes and edges

    - **nodes**: List of nodes to create
    - **edges**: List of edges to create
    - Returns summary of created elements
    """
    nodes_created = 0
    edges_created = 0

    # Create nodes
    for node in request.nodes:
        if node.id not in graph_storage["nodes"]:
            graph_storage["nodes"][node.id] = node
            nodes_created += 1

    # Create edges
    for edge in request.edges:
        # Validate source and target nodes exist
        if edge.source not in graph_storage["nodes"]:
            raise HTTPException(
                status_code=400,
                detail=f"Source node {edge.source} does not exist"
            )
        if edge.target not in graph_storage["nodes"]:
            raise HTTPException(
                status_code=400,
                detail=f"Target node {edge.target} does not exist"
            )

        if edge.id not in graph_storage["edges"]:
            graph_storage["edges"][edge.id] = edge
            edges_created += 1

    return {
        "nodes_created": nodes_created,
        "edges_created": edges_created,
        "message": f"Created {nodes_created} nodes and {edges_created} edges"
    }


@router.post("/query", response_model=GraphResponse)
async def query_graph(request: GraphQueryRequest):
    """
    Query the knowledge graph using Cypher-like syntax

    - **query**: Query string
    - **parameters**: Optional query parameters
    - Returns matching nodes and edges
    """
    # Simplified query implementation for demo
    # In production, this would connect to Neo4j

    nodes = []
    edges = []

    # Simple pattern matching for demo
    if "MATCH" in request.query and "RETURN" in request.query:
        # Extract node type from query (simplified)
        if "Concept" in request.query:
            nodes = [
                node for node in graph_storage["nodes"].values()
                if node.type == NodeType.CONCEPT
            ]
        else:
            nodes = list(graph_storage["nodes"].values())

        # Get related edges
        node_ids = {node.id for node in nodes}
        edges = [
            edge for edge in graph_storage["edges"].values()
            if edge.source in node_ids or edge.target in node_ids
        ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        metadata={
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "query": request.query
        }
    )


@router.post("/traverse")
async def traverse_graph(request: GraphTraversalRequest):
    """
    Traverse the graph starting from a node

    - **start_node**: ID of the starting node
    - **direction**: Traversal direction (incoming, outgoing, both)
    - **max_depth**: Maximum traversal depth
    - **relation_types**: Optional filter by relation types
    - Returns traversal path and visited nodes/edges
    """
    if request.start_node not in graph_storage["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"Start node {request.start_node} not found"
        )

    visited_nodes = {request.start_node}
    visited_edges = set()
    path = [request.start_node]

    # Simplified BFS traversal
    current_level = {request.start_node}

    for depth in range(request.max_depth):
        next_level = set()

        for node_id in current_level:
            # Find connected edges
            for edge in graph_storage["edges"].values():
                # Filter by relation types if specified
                if request.relation_types and edge.type not in request.relation_types:
                    continue

                # Check direction
                add_edge = False
                if request.direction in ["both", "outgoing"] and edge.source == node_id:
                    next_level.add(edge.target)
                    add_edge = True
                elif request.direction in ["both", "incoming"] and edge.target == node_id:
                    next_level.add(edge.source)
                    add_edge = True

                if add_edge:
                    visited_edges.add(edge.id)
                    visited_nodes.update([edge.source, edge.target])

        current_level = next_level - visited_nodes
        if current_level:
            path.extend(list(current_level)[:5])  # Limit path length for demo
        else:
            break

    return {
        "path": path,
        "nodes": [
            graph_storage["nodes"][node_id]
            for node_id in visited_nodes
            if node_id in graph_storage["nodes"]
        ],
        "edges": [
            graph_storage["edges"][edge_id]
            for edge_id in visited_edges
            if edge_id in graph_storage["edges"]
        ],
        "metadata": {
            "depth": depth + 1,
            "nodes_visited": len(visited_nodes),
            "edges_visited": len(visited_edges)
        }
    }


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    """
    Get a specific node by ID

    - **node_id**: Node identifier
    - Returns node details
    """
    if node_id not in graph_storage["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"Node {node_id} not found"
        )

    return graph_storage["nodes"][node_id]


@router.get("/nodes")
async def list_nodes(
    node_type: NodeType = None,
    limit: int = 100
):
    """
    List all nodes with optional filtering

    - **node_type**: Optional filter by node type
    - **limit**: Maximum number of nodes to return
    - Returns list of nodes
    """
    nodes = list(graph_storage["nodes"].values())

    if node_type:
        nodes = [n for n in nodes if n.type == node_type]

    return {
        "nodes": nodes[:limit],
        "total": len(nodes),
        "filtered": len(nodes)
    }


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    """
    Delete a node and its connected edges

    - **node_id**: Node identifier
    - Returns success message
    """
    if node_id not in graph_storage["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"Node {node_id} not found"
        )

    # Remove connected edges
    edges_to_remove = [
        edge_id for edge_id, edge in graph_storage["edges"].items()
        if edge.source == node_id or edge.target == node_id
    ]

    for edge_id in edges_to_remove:
        del graph_storage["edges"][edge_id]

    # Remove node
    del graph_storage["nodes"][node_id]

    return {
        "message": "Node deleted successfully",
        "edges_removed": len(edges_to_remove)
    }
