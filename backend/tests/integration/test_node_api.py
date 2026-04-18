"""Integration tests for P1 node and concept-context APIs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.graph_service import GraphService
from app.services.node_service import NodeService, get_node_service


def _write_context_graph(root: Path, graph_id: str = "graph-task-context") -> str:
    graph_dir = root / graph_id / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [
            {
                "id": "concept_pid",
                "label": "PID Controller",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
                "source_location": "Section 4.1",
                "community": 1,
            },
            {
                "id": "concept_feedback",
                "label": "Feedback Control",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
                "source_location": "Section 2.1",
                "community": 1,
            },
            {
                "id": "concept_stability",
                "label": "Closed-Loop Stability",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
                "source_location": "Section 4.4",
                "community": 1,
            },
            {
                "id": "formula_pid",
                "label": "u(t)=Kp e(t)+Ki ∫e(t)dt+Kd de(t)/dt",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
                "source_location": "Eq. 4.3",
                "community": 1,
            },
            {
                "id": "example_cruise",
                "label": "Example: Cruise Control",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
                "source_location": "Example 4.1",
                "community": 1,
            },
        ],
        "links": [
            {
                "source": "concept_pid",
                "target": "concept_feedback",
                "relation": "depends_on",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
            },
            {
                "source": "concept_pid",
                "target": "concept_stability",
                "relation": "related_to",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
            },
            {
                "source": "concept_pid",
                "target": "formula_pid",
                "relation": "defines",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
            },
            {
                "source": "example_cruise",
                "target": "concept_pid",
                "relation": "example_of",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
            },
        ],
    }
    (graph_dir / "graph.json").write_text(json.dumps(payload), encoding="utf-8")
    (graph_dir / "source_chunks.json").write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_id": "sample-1",
                        "source_file": "raw/sample.pdf",
                        "source_location": "Section 4.1",
                        "page_start": 4,
                        "page_end": 4,
                        "text": "PID controller adjusts control effort based on proportional, integral, and derivative actions.",
                    },
                    {
                        "chunk_id": "sample-2",
                        "source_file": "raw/sample.pdf",
                        "source_location": "Section 2.1",
                        "page_start": 2,
                        "page_end": 2,
                        "text": "Feedback control compares the output with the reference signal.",
                    },
                    {
                        "chunk_id": "sample-3",
                        "source_file": "raw/sample.pdf",
                        "source_location": "Section 4.4",
                        "page_start": 7,
                        "page_end": 7,
                        "text": "Closed-loop stability depends on the pole locations of the controlled system.",
                    },
                    {
                        "chunk_id": "sample-4",
                        "source_file": "raw/sample.pdf",
                        "source_location": "Eq. 4.3",
                        "page_start": 5,
                        "page_end": 5,
                        "text": "u(t)=Kp e(t)+Ki ∫e(t)dt+Kd de(t)/dt",
                    },
                    {
                        "chunk_id": "sample-5",
                        "source_file": "raw/sample.pdf",
                        "source_location": "Example 4.1",
                        "page_start": 6,
                        "page_end": 6,
                        "text": "Cruise control is a common textbook example of PID regulation.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (graph_dir / "GRAPH_REPORT.md").write_text("# report\n", encoding="utf-8")
    return graph_id


@pytest.fixture
def client(tmp_path: Path):
    graph_id = _write_context_graph(tmp_path)
    service = NodeService(
        GraphService(
            artifacts_root=tmp_path,
            driver_factory=lambda: (_ for _ in ()).throw(RuntimeError("neo4j disabled")),
        )
    )
    app.dependency_overrides[get_node_service] = lambda: service
    try:
        yield TestClient(app), graph_id
    finally:
        app.dependency_overrides.clear()


class TestNodeAPI:
    """Validate P1 node routes."""

    def test_get_node_detail(self, client):
        api_client, graph_id = client

        response = api_client.get(f"/api/node/concept_pid?graphId={graph_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "concept_pid"
        assert data["nodeType"] == "concept"
        assert data["metadata"]["graphSource"] == "artifact"

    def test_get_node_neighbors(self, client):
        api_client, graph_id = client

        response = api_client.get(f"/api/node/concept_pid/neighbors?graphId={graph_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["total"] == 4
        assert {item["node"]["id"] for item in data["items"]} == {
            "concept_feedback",
            "concept_stability",
            "formula_pid",
            "example_cruise",
        }

    def test_search_and_fulltext(self, client):
        api_client, graph_id = client

        search_response = api_client.get(f"/api/node/search?graphId={graph_id}&q=PID")
        fulltext_response = api_client.get(f"/api/node/fulltext?graphId={graph_id}&q=stability")

        assert search_response.status_code == 200
        assert search_response.json()["items"][0]["id"] == "concept_pid"
        assert fulltext_response.status_code == 200
        assert fulltext_response.json()["items"][0]["id"] == "concept_stability"

    def test_semantic_search(self, client):
        api_client, graph_id = client

        response = api_client.post(
            "/api/node/semantic",
            json={
                "graphId": graph_id,
                "query": "How does feedback improve PID stability?",
                "limit": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["strategy"] == "keyword_extraction_fulltext_fallback"
        assert len(data["items"]) >= 2

    def test_tutor_concept_context(self, client):
        api_client, graph_id = client

        response = api_client.get(f"/api/tutor/concept/concept_pid/context?graphId={graph_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["concept"]["id"] == "concept_pid"
        assert [item["id"] for item in data["prerequisites"]] == ["concept_feedback"]
        assert [item["id"] for item in data["formulas"]] == ["formula_pid"]
        assert [item["id"] for item in data["examples"]] == ["example_cruise"]
        assert any(passage["sourceLocation"] == "Section 4.1" for passage in data["passages"])
        assert any("Feedback control compares the output" in passage["text"] for passage in data["passages"])