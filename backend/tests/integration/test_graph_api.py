"""
Integration tests for Graph API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.schemas.graph import NodeType, RelationType


class TestGraphCreateAPI:
    """Test graph creation endpoint"""

    def test_create_graph_elements(self, client: TestClient):
        """Test creating graph nodes and edges"""
        request_data = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "concept",
                    "label": "Control System"
                },
                {
                    "id": "node-2",
                    "type": "formula",
                    "label": "Transfer Function"
                }
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-2",
                    "type": "defines"
                }
            ]
        }

        response = client.post("/api/graph/create", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "nodes_created" in data
        assert "edges_created" in data
        assert data["nodes_created"] == 2
        assert data["edges_created"] == 1

    def test_create_empty_graph(self, client: TestClient):
        """Test creating empty graph"""
        request_data = {"nodes": [], "edges": []}

        response = client.post("/api/graph/create", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["nodes_created"] == 0
        assert data["edges_created"] == 0


class TestGraphQueryAPI:
    """Test graph query endpoint"""

    def test_query_graph(self, client: TestClient):
        """Test querying the graph"""
        # First create some nodes
        create_request = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "concept",
                    "label": "Control System"
                }
            ],
            "edges": []
        }
        client.post("/api/graph/create", json=create_request)

        # Then query
        query_request = {
            "query": "MATCH (n:Concept) RETURN n",
            "parameters": {}
        }

        response = client.post("/api/graph/query", json=query_request)

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


class TestGraphTraversalAPI:
    """Test graph traversal endpoint"""

    def test_traverse_graph(self, client: TestClient):
        """Test traversing the graph"""
        # First create nodes and edges
        create_request = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "concept",
                    "label": "Control System"
                },
                {
                    "id": "node-2",
                    "type": "formula",
                    "label": "Transfer Function"
                }
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-2",
                    "type": "defines"
                }
            ]
        }
        client.post("/api/graph/create", json=create_request)

        # Then traverse
        traversal_request = {
            "start_node": "node-1",
            "direction": "outgoing",
            "max_depth": 2
        }

        response = client.post("/api/graph/traverse", json=traversal_request)

        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "nodes" in data
        assert "edges" in data


class TestGraphGetAPI:
    """Test graph retrieval endpoints"""

    def test_get_node(self, client: TestClient):
        """Test getting a specific node"""
        # First create a node
        create_request = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "concept",
                    "label": "Control System"
                }
            ],
            "edges": []
        }
        client.post("/api/graph/create", json=create_request)

        # Then get it
        response = client.get("/api/graph/nodes/node-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "node-1"
        assert data["label"] == "Control System"

    def test_get_nonexistent_node(self, client: TestClient):
        """Test getting non-existent node"""
        response = client.get("/api/graph/nodes/nonexistent")

        assert response.status_code == 404


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app
    return TestClient(app)
