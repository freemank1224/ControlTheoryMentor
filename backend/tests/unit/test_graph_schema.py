"""
Unit tests for Graph schema
"""
import pytest
from pydantic import ValidationError
from app.schemas.graph import (
    GraphNode,
    GraphEdge,
    GraphCreateRequest,
    GraphQueryRequest,
    GraphResponse,
    NodeType,
    RelationType
)


class TestGraphNode:
    """Test GraphNode schema"""

    def test_graph_node_success(self):
        """Test successful graph node creation"""
        node = GraphNode(
            id="node-1",
            type=NodeType.CONCEPT,
            label="Control System",
            properties={"difficulty": "medium"}
        )
        assert node.id == "node-1"
        assert node.type == NodeType.CONCEPT
        assert node.label == "Control System"
        assert node.properties["difficulty"] == "medium"

    def test_graph_node_default_properties(self):
        """Test graph node with default properties"""
        node = GraphNode(
            id="node-2",
            type=NodeType.FORMULA,
            label="Transfer Function"
        )
        assert node.properties == {}


class TestGraphEdge:
    """Test GraphEdge schema"""

    def test_graph_edge_success(self):
        """Test successful graph edge creation"""
        edge = GraphEdge(
            id="edge-1",
            source="node-1",
            target="node-2",
            type=RelationType.DEFINES,
            properties={"strength": 0.9}
        )
        assert edge.id == "edge-1"
        assert edge.source == "node-1"
        assert edge.target == "node-2"
        assert edge.type == RelationType.DEFINES
        assert edge.properties["strength"] == 0.9

    def test_graph_edge_invalid_relation(self):
        """Test graph edge with invalid relation type"""
        with pytest.raises(ValidationError):
            GraphEdge(
                id="edge-1",
                source="node-1",
                target="node-2",
                type="invalid_relation"
            )


class TestGraphCreateRequest:
    """Test GraphCreateRequest schema"""

    def test_graph_create_request_success(self):
        """Test successful graph create request"""
        request = GraphCreateRequest(
            nodes=[
                GraphNode(
                    id="node-1",
                    type=NodeType.CONCEPT,
                    label="Control System"
                )
            ],
            edges=[
                GraphEdge(
                    id="edge-1",
                    source="node-1",
                    target="node-2",
                    type=RelationType.RELATED_TO
                )
            ]
        )
        assert len(request.nodes) == 1
        assert len(request.edges) == 1

    def test_graph_create_request_empty(self):
        """Test graph create request with empty nodes and edges"""
        request = GraphCreateRequest()
        assert request.nodes == []
        assert request.edges == []


class TestGraphQueryRequest:
    """Test GraphQueryRequest schema"""

    def test_graph_query_request_success(self):
        """Test successful graph query request"""
        request = GraphQueryRequest(
            query="MATCH (n:Concept) RETURN n"
        )
        assert request.query == "MATCH (n:Concept) RETURN n"
        assert request.parameters == {}

    def test_graph_query_request_with_parameters(self):
        """Test graph query request with parameters"""
        request = GraphQueryRequest(
            query="MATCH (n:Concept {name: $name}) RETURN n",
            parameters={"name": "Control System"}
        )
        assert request.parameters["name"] == "Control System"

    def test_graph_query_request_missing_query(self):
        """Test graph query request without query"""
        with pytest.raises(ValidationError):
            GraphQueryRequest()


class TestGraphResponse:
    """Test GraphResponse schema"""

    def test_graph_response_success(self):
        """Test successful graph response"""
        response = GraphResponse(
            nodes=[
                GraphNode(
                    id="node-1",
                    type=NodeType.CONCEPT,
                    label="Control System"
                )
            ],
            edges=[
                GraphEdge(
                    id="edge-1",
                    source="node-1",
                    target="node-2",
                    type=RelationType.RELATED_TO
                )
            ],
            metadata={"total_nodes": 1, "total_edges": 1}
        )
        assert len(response.nodes) == 1
        assert len(response.edges) == 1
        assert response.metadata["total_nodes"] == 1

    def test_graph_response_empty(self):
        """Test graph response with empty results"""
        response = GraphResponse()
        assert response.nodes == []
        assert response.edges == []
        assert response.metadata == {}
