"""Unit tests for NodeService graph lookup and concept context aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.graph_service import GraphService
from app.services.node_service import NodeService


def _write_context_graph(root: Path, graph_id: str = "graph-task-context") -> str:
    graph_dir = root / graph_id / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [
            {
                "id": "paper_1",
                "label": "Modern Control Systems",
                "file_type": "paper",
                "source_file": "raw/sample.pdf",
            },
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


class TestNodeService:
    """Validate tutor-facing concept lookup behavior."""

    def test_get_concept_context_groups_related_nodes(self, tmp_path: Path):
        graph_id = _write_context_graph(tmp_path)
        service = NodeService(GraphService(artifacts_root=tmp_path, driver_factory=lambda: (_ for _ in ()).throw(RuntimeError("neo4j disabled"))))

        context = service.get_concept_context(graph_id, "concept_pid")

        assert context["concept"]["label"] == "PID Controller"
        assert [node["id"] for node in context["prerequisites"]] == ["concept_feedback"]
        assert [node["id"] for node in context["formulas"]] == ["formula_pid"]
        assert [node["id"] for node in context["examples"]] == ["example_cruise"]
        assert [node["id"] for node in context["relatedNodes"]] == ["concept_stability"]
        assert {passage["sourceLocation"] for passage in context["passages"]} >= {"Section 4.1", "Section 2.1"}
        assert any("PID controller adjusts control effort" in passage["text"] for passage in context["passages"])
        assert context["lookup"]["semanticSearchStrategy"] == "keyword_extraction_fulltext_fallback"

    def test_semantic_search_uses_keyword_fallback(self, tmp_path: Path):
        graph_id = _write_context_graph(tmp_path)
        service = NodeService(GraphService(artifacts_root=tmp_path, driver_factory=lambda: (_ for _ in ()).throw(RuntimeError("neo4j disabled"))))

        response = service.semantic_search(graph_id, "How does PID feedback improve stability?", limit=3)

        assert {item["id"] for item in response["items"]} >= {"concept_feedback", "concept_stability"}
        assert response["metadata"]["strategy"] == "keyword_extraction_fulltext_fallback"
        assert "feedback" in response["metadata"]["keywords"]