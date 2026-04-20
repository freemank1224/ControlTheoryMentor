"""Unit tests for GraphService artifact and fallback behavior."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.graph_service import GraphService


def _write_graphify_artifact(root: Path, graph_id: str = "graph-task-fixture") -> str:
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
        ],
        "links": [
            {
                "source": "concept_pid",
                "target": "concept_feedback",
                "relation": "depends_on",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
            }
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
                        "text": "PID controller text.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (graph_dir / "GRAPH_REPORT.md").write_text("# report\n", encoding="utf-8")
    return graph_id


class TestGraphService:
    """Validate graph artifact loading and legacy fallback behavior."""

    def test_get_graph_view_reads_graphify_artifact(self, tmp_path: Path):
        graph_id = _write_graphify_artifact(tmp_path)
        service = GraphService(artifacts_root=tmp_path)

        response = service.get_graph_view(graph_id)

        assert response["metadata"]["graphId"] == graph_id
        assert response["metadata"]["source"] == "artifact"
        assert response["metadata"]["sourceChunksPath"].endswith("source_chunks.json")
        assert response["metadata"]["total_nodes"] == 2
        assert response["metadata"]["total_edges"] == 1
        assert response["elements"]["nodes"][0]["data"]["label"] == "PID Controller"
        assert response["metadata"]["domainCompatibility"]["expectedDomain"] == "control_theory"
        assert response["metadata"]["domainCompatibility"]["compatible"] is True

    def test_get_graph_snapshot_falls_back_to_legacy_json(self, tmp_path: Path):
        graph_id = "legacy-graph"
        legacy_payload = {
            "nodes": {
                "node-1": {"id": "node-1", "label": "Legacy Concept", "type": "concept"},
            },
            "edges": {
                "edge-1": {
                    "id": "edge-1",
                    "source": "node-1",
                    "target": "node-1",
                    "type": "related_to",
                }
            },
        }
        (tmp_path / f"{graph_id}.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
        service = GraphService(artifacts_root=tmp_path)

        snapshot = service.get_graph_snapshot(graph_id)

        assert snapshot.source == "legacy"
        assert "node-1" in snapshot.nodes_by_id
        assert snapshot.edges[0]["relation"] == "related_to"

    def test_get_graph_domain_compatibility_flags_non_control_graph(self, tmp_path: Path):
        graph_id = "graph-other-domain"
        graph_dir = tmp_path / graph_id / "graphify-out"
        graph_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [
                {
                    "id": "concept_biology",
                    "label": "Cell Membrane",
                    "file_type": "paper",
                    "source_file": "raw/biology.pdf",
                    "source_location": "Chapter 1",
                }
            ],
            "links": [],
        }
        (graph_dir / "graph.json").write_text(json.dumps(payload), encoding="utf-8")

        service = GraphService(artifacts_root=tmp_path)
        compatibility = service.get_graph_domain_compatibility(graph_id)

        assert compatibility["expectedDomain"] == "control_theory"
        assert compatibility["compatible"] is False
        assert compatibility["reason"] == "domain_mismatch"