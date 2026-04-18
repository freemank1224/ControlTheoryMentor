"""Graph access services backed by Graphify artifacts with optional Neo4j enrichment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.config import settings
from app.db.neo4j import get_driver


class GraphServiceError(RuntimeError):
    """Base error for graph lookup failures."""


class GraphNotFoundError(GraphServiceError):
    """Raised when a graph artifact cannot be found."""


class NodeNotFoundError(GraphServiceError):
    """Raised when a node cannot be found in the graph."""


@dataclass(frozen=True)
class GraphSnapshot:
    """Normalized graph artifact ready for API consumption."""

    graph_id: str
    source: str
    artifact_path: str | None
    report_path: str | None
    source_chunks_path: str | None
    nodes_by_id: dict[str, dict[str, Any]]
    edges: list[dict[str, Any]]
    source_chunks: list[dict[str, Any]]


class GraphService:
    """Read graph data from Graphify artifacts and map it into stable API models."""

    def __init__(
        self,
        artifacts_root: str | Path | None = None,
        driver_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.artifacts_root = Path(artifacts_root or settings.GRAPH_ARTIFACTS_PATH)
        self.driver_factory = driver_factory or get_driver

    def get_graph_snapshot(self, graph_id: str) -> GraphSnapshot:
        """Load a graph artifact, falling back to the legacy JSON shape if needed."""
        artifact_path = self.artifacts_root / graph_id / "graphify-out" / "graph.json"
        report_path = self.artifacts_root / graph_id / "graphify-out" / "GRAPH_REPORT.md"
        source_chunks_path = self.artifacts_root / graph_id / "graphify-out" / "source_chunks.json"
        if artifact_path.exists():
            payload = self._read_json(artifact_path)
            return self._build_snapshot(
                graph_id=graph_id,
                payload=payload,
                source="artifact",
                artifact_path=str(artifact_path),
                report_path=str(report_path) if report_path.exists() else None,
                source_chunks_path=str(source_chunks_path) if source_chunks_path.exists() else None,
            )

        legacy_path = self.artifacts_root / f"{graph_id}.json"
        if legacy_path.exists():
            payload = self._read_json(legacy_path)
            return self._build_snapshot(
                graph_id=graph_id,
                payload=payload,
                source="legacy",
                artifact_path=str(legacy_path),
                report_path=None,
                source_chunks_path=None,
            )

        raise GraphNotFoundError(f"Graph {graph_id} not found")

    def get_graph_view(self, graph_id: str) -> dict[str, Any]:
        """Return a Cytoscape-compatible graph view for the frontend graph panel."""
        snapshot = self.get_graph_snapshot(graph_id)
        nodes = [
            {
                "data": {
                    "id": node["id"],
                    "label": node["label"],
                    "type": node.get("fileType", "unknown"),
                    "source_file": node.get("sourceFile", ""),
                    "community": node.get("community"),
                }
            }
            for node in snapshot.nodes_by_id.values()
        ]
        edges = [
            {
                "data": {
                    "id": edge["id"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "label": edge["relation"],
                    "relation": edge["relation"],
                    "confidence": edge.get("confidence", "EXTRACTED"),
                }
            }
            for edge in snapshot.edges
        ]
        return {
            "elements": {
                "nodes": nodes,
                "edges": edges,
            },
            "metadata": {
                "graphId": graph_id,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "reportPath": snapshot.report_path,
                "sourceChunksPath": snapshot.source_chunks_path,
                "source": snapshot.source,
            },
        }

    def get_node(self, graph_id: str, node_id: str) -> tuple[GraphSnapshot, dict[str, Any]]:
        """Return a normalized node from a graph snapshot."""
        snapshot = self.get_graph_snapshot(graph_id)
        node = snapshot.nodes_by_id.get(node_id)
        if node is None:
            raise NodeNotFoundError(f"Node {node_id} not found in graph {graph_id}")
        return snapshot, node

    def get_optional_neo4j_node(self, node_id: str) -> dict[str, Any] | None:
        """Best-effort Neo4j lookup mapped onto the same normalized node shape."""
        try:
            driver = self.driver_factory()
        except Exception:
            return None

        try:
            with driver.session() as session:
                record = session.run(
                    "MATCH (n {id: $node_id}) RETURN properties(n) AS node LIMIT 1",
                    node_id=node_id,
                ).single()
        except (Neo4jError, ServiceUnavailable):
            return None

        if not record or not record.get("node"):
            return None
        return self._normalize_node(record["node"])

    def neo4j_available(self) -> bool:
        """Indicate whether a Neo4j driver could be resolved for enrichment."""
        try:
            self.driver_factory()
        except Exception:
            return False
        return True

    def _build_snapshot(
        self,
        graph_id: str,
        payload: dict[str, Any],
        source: str,
        artifact_path: str | None,
        report_path: str | None,
        source_chunks_path: str | None,
    ) -> GraphSnapshot:
        raw_nodes = payload.get("nodes", [])
        if isinstance(raw_nodes, dict):
            raw_nodes = list(raw_nodes.values())
        nodes = [self._normalize_node(node) for node in raw_nodes]
        nodes_by_id = {node["id"]: node for node in nodes if node["id"]}

        raw_edges = payload.get("links", []) or payload.get("edges", [])
        if isinstance(raw_edges, dict):
            raw_edges = list(raw_edges.values())
        edges = [
            edge
            for edge in (self._normalize_edge(index, edge) for index, edge in enumerate(raw_edges, start=1))
            if edge["source"] in nodes_by_id and edge["target"] in nodes_by_id
        ]

        source_chunks = []
        if source_chunks_path:
            source_chunks_payload = self._read_json(Path(source_chunks_path))
            source_chunks = list(source_chunks_payload.get("chunks", []))

        return GraphSnapshot(
            graph_id=graph_id,
            source=source,
            artifact_path=artifact_path,
            report_path=report_path,
            source_chunks_path=source_chunks_path,
            nodes_by_id=nodes_by_id,
            edges=edges,
            source_chunks=source_chunks,
        )

    def _normalize_node(self, raw_node: dict[str, Any]) -> dict[str, Any]:
        if "data" in raw_node and isinstance(raw_node["data"], dict):
            raw_node = raw_node["data"]

        node_id = str(raw_node.get("id") or "")
        reserved = {
            "id",
            "label",
            "type",
            "file_type",
            "source_file",
            "source_location",
            "community",
            "properties",
        }
        properties = dict(raw_node.get("properties") or {})
        for key, value in raw_node.items():
            if key not in reserved and key not in properties:
                properties[key] = value

        return {
            "id": node_id,
            "label": str(raw_node.get("label") or node_id),
            "fileType": str(raw_node.get("file_type") or raw_node.get("type") or "unknown"),
            "rawType": raw_node.get("type"),
            "sourceFile": raw_node.get("source_file") or "",
            "sourceLocation": raw_node.get("source_location"),
            "community": raw_node.get("community"),
            "properties": properties,
        }

    def _normalize_edge(self, index: int, raw_edge: dict[str, Any]) -> dict[str, Any]:
        if "data" in raw_edge and isinstance(raw_edge["data"], dict):
            raw_edge = raw_edge["data"]

        source = str(raw_edge.get("_src") or raw_edge.get("source") or "")
        target = str(raw_edge.get("_tgt") or raw_edge.get("target") or "")
        relation = str(raw_edge.get("relation") or raw_edge.get("label") or "related_to")
        edge_id = str(raw_edge.get("id") or f"{source}-{relation}-{target}-{index}")
        reserved = {
            "id",
            "source",
            "target",
            "_src",
            "_tgt",
            "label",
            "relation",
            "confidence",
            "confidence_score",
            "weight",
            "source_file",
            "source_location",
            "properties",
        }
        properties = dict(raw_edge.get("properties") or {})
        for key, value in raw_edge.items():
            if key not in reserved and key not in properties:
                properties[key] = value

        return {
            "id": edge_id,
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": str(raw_edge.get("confidence") or "EXTRACTED"),
            "confidenceScore": raw_edge.get("confidence_score"),
            "weight": raw_edge.get("weight"),
            "sourceFile": raw_edge.get("source_file") or "",
            "sourceLocation": raw_edge.get("source_location"),
            "properties": properties,
        }

    @staticmethod
    def _read_json(file_path: Path) -> dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)


def get_graph_service() -> GraphService:
    """FastAPI dependency for the graph service."""
    return GraphService()