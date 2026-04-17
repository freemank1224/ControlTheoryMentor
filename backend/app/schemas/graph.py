"""
Graph schemas for knowledge graph models
"""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Graph node types"""
    CONCEPT = "concept"
    FORMULA = "formula"
    EXAMPLE = "example"
    PROBLEM = "problem"
    REFERENCE = "reference"


class RelationType(str, Enum):
    """Graph edge relation types"""
    DEFINES = "defines"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    EXAMPLE_OF = "example_of"
    SOLVES = "solves"
    REFERENCES = "references"


class GraphNode(BaseModel):
    """Graph node model"""
    id: str = Field(..., description="Unique node identifier")
    type: NodeType = Field(..., description="Node type")
    label: str = Field(..., description="Node label")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Node properties")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "node-1",
                "type": "concept",
                "label": "Control System",
                "properties": {
                    "difficulty": "medium"
                }
            }
        }


class GraphEdge(BaseModel):
    """Graph edge model"""
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: RelationType = Field(..., description="Relation type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge properties")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "edge-1",
                "source": "node-1",
                "target": "node-2",
                "type": "defines",
                "properties": {
                    "strength": 0.9
                }
            }
        }


class GraphCreateRequest(BaseModel):
    """Request model for creating graph elements"""
    nodes: List[GraphNode] = Field(default_factory=list, description="Nodes to create")
    edges: List[GraphEdge] = Field(default_factory=list, description="Edges to create")

    class Config:
        json_schema_extra = {
            "example": {
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "concept",
                        "label": "Control System"
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "node-1",
                        "target": "node-2",
                        "type": "related_to"
                    }
                ]
            }
        }


class GraphQueryRequest(BaseModel):
    """Request model for querying the graph"""
    query: str = Field(..., description="Cypher query string")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "MATCH (n:Concept {name: $name}) RETURN n",
                "parameters": {
                    "name": "Control System"
                }
            }
        }


class GraphResponse(BaseModel):
    """Response model for graph queries"""
    nodes: List[GraphNode] = Field(default_factory=list, description="Graph nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Graph edges")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "concept",
                        "label": "Control System",
                        "properties": {}
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "node-1",
                        "target": "node-2",
                        "type": "related_to",
                        "properties": {}
                    }
                ],
                "metadata": {
                    "total_nodes": 1,
                    "total_edges": 1
                }
            }
        }


class GraphTraversalRequest(BaseModel):
    """Request model for graph traversal"""
    start_node: str = Field(..., description="Starting node ID")
    direction: str = Field(default="both", description="Traversal direction: incoming, outgoing, or both")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum traversal depth")
    relation_types: List[RelationType] = Field(default_factory=list, description="Filter by relation types")

    class Config:
        json_schema_extra = {
            "example": {
                "start_node": "node-1",
                "direction": "outgoing",
                "max_depth": 2,
                "relation_types": ["defines", "related_to"]
            }
        }
