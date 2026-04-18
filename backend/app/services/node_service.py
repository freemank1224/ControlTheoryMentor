"""Node and concept-context services for tutor-facing graph access."""

from __future__ import annotations

import re
from typing import Any

from app.services.graph_service import GraphService, NodeNotFoundError, get_graph_service


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "why",
    "with",
}

PREREQUISITE_RELATIONS = {"depends_on", "requires", "prerequisite", "builds_on", "derived_from"}
FORMULA_RELATIONS = {"defines", "uses_formula", "expressed_by"}
EXAMPLE_RELATIONS = {"example_of", "illustrates", "applies_to"}


class NodeService:
    """Tutor-facing node lookup and concept context aggregation."""

    def __init__(self, graph_service: GraphService | None = None) -> None:
        self.graph_service = graph_service or get_graph_service()

    def get_node_detail(self, graph_id: str, node_id: str) -> dict[str, Any]:
        snapshot, node = self.graph_service.get_node(graph_id, node_id)
        enriched = self.graph_service.get_optional_neo4j_node(node_id)
        detail = self._serialize_node(graph_id, node, score=None, match_reason=None)
        detail["metadata"] = {
            "graphSource": snapshot.source,
            "artifactPath": snapshot.artifact_path,
            "reportPath": snapshot.report_path,
            "neo4jEnriched": enriched is not None,
        }
        if enriched:
            merged_properties = dict(enriched.get("properties") or {})
            merged_properties.update(detail["properties"])
            detail["properties"] = merged_properties
        return detail

    def get_neighbors(self, graph_id: str, node_id: str, limit: int = 25) -> dict[str, Any]:
        snapshot, node = self.graph_service.get_node(graph_id, node_id)
        items: list[dict[str, Any]] = []

        for edge in snapshot.edges:
            direction = None
            neighbor_id = None
            if edge["source"] == node_id:
                direction = "outgoing"
                neighbor_id = edge["target"]
            elif edge["target"] == node_id:
                direction = "incoming"
                neighbor_id = edge["source"]

            if direction is None or neighbor_id not in snapshot.nodes_by_id:
                continue

            items.append(
                {
                    "direction": direction,
                    "node": self._serialize_node(graph_id, snapshot.nodes_by_id[neighbor_id], score=None, match_reason=None),
                    "edge": {
                        "id": edge["id"],
                        "relation": edge["relation"],
                        "confidence": edge["confidence"],
                        "confidenceScore": edge.get("confidenceScore"),
                        "weight": edge.get("weight"),
                        "sourceLocation": edge.get("sourceLocation"),
                        "sourceFile": edge.get("sourceFile", ""),
                        "properties": edge.get("properties", {}),
                    },
                }
            )

        items.sort(key=lambda item: (item["direction"], item["node"]["label"].lower()))
        return {
            "graphId": graph_id,
            "node": self._serialize_node(graph_id, node, score=None, match_reason=None),
            "items": items[:limit],
            "metadata": {
                "total": len(items),
                "limit": limit,
                "graphSource": snapshot.source,
            },
        }

    def search_nodes(self, graph_id: str, query: str, limit: int = 10, mode: str = "search") -> dict[str, Any]:
        snapshot = self.graph_service.get_graph_snapshot(graph_id)
        normalized_query = query.strip().lower()
        results: list[dict[str, Any]] = []

        for node in snapshot.nodes_by_id.values():
            score, reason = self._score_node(snapshot, node, normalized_query, mode)
            if score <= 0:
                continue
            results.append(self._serialize_node(graph_id, node, score=round(score, 4), match_reason=reason))

        results.sort(key=lambda item: (-float(item["score"] or 0), item["label"].lower()))
        return {
            "graphId": graph_id,
            "query": query,
            "items": results[:limit],
            "metadata": {
                "mode": mode,
                "total": len(results),
                "limit": limit,
                "graphSource": snapshot.source,
            },
        }

    def semantic_search(self, graph_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        snapshot = self.graph_service.get_graph_snapshot(graph_id)
        normalized_query = query.strip().lower()
        keywords = [
            token
            for token in re.findall(r"[a-zA-Z0-9_+-]+", normalized_query)
            if len(token) >= 3 and token not in STOPWORDS
        ]
        results: list[dict[str, Any]] = []

        for node in snapshot.nodes_by_id.values():
            base_score, reason = self._score_node(snapshot, node, normalized_query, mode="fulltext")
            keyword_hits = 0
            for keyword in keywords:
                keyword_score, _ = self._score_node(snapshot, node, keyword, mode="fulltext")
                if keyword_score > 0:
                    keyword_hits += 1
                    base_score = max(base_score, keyword_score) + 0.1
            if base_score <= 0:
                continue
            match_reason = reason or "keyword_fallback"
            if keyword_hits:
                match_reason = f"keyword_overlap:{keyword_hits}"
            results.append(self._serialize_node(graph_id, node, score=round(base_score, 4), match_reason=match_reason))

        results.sort(key=lambda item: (-float(item["score"] or 0), item["label"].lower()))
        return {
            "graphId": graph_id,
            "query": query,
            "items": results[:limit],
            "metadata": {
                "mode": "semantic",
                "strategy": "keyword_extraction_fulltext_fallback",
                "keywords": keywords,
                "total": len(results),
                "limit": limit,
                "graphSource": snapshot.source,
            },
        }

    def get_concept_context(self, graph_id: str, node_id: str) -> dict[str, Any]:
        snapshot, node = self.graph_service.get_node(graph_id, node_id)
        neighbors_payload = self.get_neighbors(graph_id, node_id, limit=100)
        prerequisites: list[dict[str, Any]] = []
        related_nodes: list[dict[str, Any]] = []
        formulas: list[dict[str, Any]] = []
        examples: list[dict[str, Any]] = []
        source_sections: list[dict[str, Any]] = []
        passages: list[dict[str, Any]] = []
        seen_sections: set[tuple[str, str | None]] = set()
        seen_passages: set[tuple[str, str | None]] = set()

        concept = self._serialize_node(graph_id, node, score=None, match_reason=None)
        self._append_source_section(source_sections, seen_sections, concept)
        self._append_passage(passages, seen_passages, snapshot, concept)

        for item in neighbors_payload["items"]:
            relation = item["edge"]["relation"].lower()
            neighbor = item["node"]
            self._append_source_section(source_sections, seen_sections, neighbor)
            self._append_passage(passages, seen_passages, snapshot, neighbor)

            if relation in PREREQUISITE_RELATIONS:
                prerequisites.append(neighbor)
                continue
            if relation in EXAMPLE_RELATIONS or neighbor["nodeType"] == "example":
                examples.append(neighbor)
                continue
            if relation in FORMULA_RELATIONS or neighbor["nodeType"] == "formula":
                formulas.append(neighbor)
                continue
            related_nodes.append(neighbor)

        return {
            "graphId": graph_id,
            "concept": concept,
            "prerequisites": self._dedupe_nodes(prerequisites),
            "relatedNodes": self._dedupe_nodes(related_nodes),
            "formulas": self._dedupe_nodes(formulas),
            "examples": self._dedupe_nodes(examples),
            "sourceSections": source_sections,
            "passages": passages,
            "lookup": {
                "graphId": graph_id,
                "conceptId": node_id,
                "sourcePriority": ["artifact", "neo4j_enrichment"],
                "semanticSearchStrategy": "keyword_extraction_fulltext_fallback",
                "graphSource": snapshot.source,
                "artifactPath": snapshot.artifact_path,
                "reportPath": snapshot.report_path,
                "sourceChunksPath": snapshot.source_chunks_path,
                "neo4jEnrichmentAvailable": self.graph_service.neo4j_available(),
            },
            "metadata": {
                "neighborCount": neighbors_payload["metadata"]["total"],
                "passageCount": len(passages),
                "graphSource": snapshot.source,
            },
        }

    def _serialize_node(
        self,
        graph_id: str,
        node: dict[str, Any],
        score: float | None,
        match_reason: str | None,
    ) -> dict[str, Any]:
        node_type = self._classify_node(node)
        payload = {
            "graphId": graph_id,
            "id": node["id"],
            "label": node["label"],
            "nodeType": node_type,
            "fileType": node.get("fileType", "unknown"),
            "community": node.get("community"),
            "sourceFile": node.get("sourceFile", ""),
            "sourceLocation": node.get("sourceLocation"),
            "properties": node.get("properties", {}),
            "score": score,
            "matchReason": match_reason,
        }
        return payload

    def _classify_node(self, node: dict[str, Any]) -> str:
        label = node["label"].lower()
        node_id = node["id"].lower()
        file_type = str(node.get("fileType") or "").lower()

        if label.startswith("example") or " example" in label:
            return "example"
        if any(token in label for token in ("=", "laplace", "equation", "formula", "transfer function")):
            return "formula"
        if any(node_id.startswith(prefix) for prefix in ("paper_", "document_", "image_", "code_", "rationale_")):
            return "reference"
        if file_type in {"image", "code", "rationale"}:
            return "reference"
        return "concept"

    def _score_node(self, snapshot: Any, node: dict[str, Any], query: str, mode: str) -> tuple[float, str | None]:
        if not query:
            return 0.0, None

        label = node["label"].lower()
        node_id = node["id"].lower()
        search_text = self._build_search_text(snapshot, node)
        tokens = [token for token in re.findall(r"[a-zA-Z0-9_+-]+", query) if token]

        if mode == "search":
            if query == label or query == node_id:
                return 1.0, "exact"
            if label.startswith(query):
                return 0.92, "prefix"
            if query in label:
                return 0.85, "label_contains"
            if query in node_id:
                return 0.8, "id_contains"
            if query in search_text:
                return 0.65, "property_contains"
            return 0.0, None

        matched_tokens = [token for token in tokens if token in search_text]
        if not matched_tokens:
            return 0.0, None

        coverage = len(set(matched_tokens)) / max(len(set(tokens)), 1)
        label_bonus = 0.15 if any(token in label for token in matched_tokens) else 0.0
        return min(0.95, 0.45 + coverage + label_bonus), "token_overlap"

    def _build_search_text(self, snapshot: Any, node: dict[str, Any]) -> str:
        edge_relations = []
        for edge in snapshot.edges:
            if edge["source"] == node["id"] or edge["target"] == node["id"]:
                edge_relations.append(edge["relation"])

        properties_text = " ".join(str(value) for value in node.get("properties", {}).values() if value is not None)
        return " ".join(
            part.lower()
            for part in [
                node["label"],
                node["id"],
                node.get("sourceFile", ""),
                str(node.get("sourceLocation") or ""),
                properties_text,
                " ".join(edge_relations),
            ]
            if part
        )

    @staticmethod
    def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for node in nodes:
            if node["id"] in seen:
                continue
            seen.add(node["id"])
            deduped.append(node)
        return deduped

    @staticmethod
    def _append_source_section(
        source_sections: list[dict[str, Any]],
        seen_sections: set[tuple[str, str | None]],
        node: dict[str, Any],
    ) -> None:
        source_file = node.get("sourceFile") or ""
        source_location = node.get("sourceLocation")
        key = (source_file, source_location)
        if not source_file or key in seen_sections:
            return
        seen_sections.add(key)
        source_sections.append(
            {
                "sourceFile": source_file,
                "sourceLocation": source_location,
                "sectionLabel": source_location or source_file,
            }
        )

    @staticmethod
    def _append_passage(
        passages: list[dict[str, Any]],
        seen_passages: set[tuple[str, str | None]],
        snapshot: Any,
        node: dict[str, Any],
    ) -> None:
        source_file = node.get("sourceFile") or ""
        source_location = node.get("sourceLocation")
        key = (source_file, source_location)
        if not source_file or key in seen_passages:
            return

        for chunk in snapshot.source_chunks:
            if chunk.get("source_file") != source_file:
                continue
            if chunk.get("source_location") != source_location:
                continue
            seen_passages.add(key)
            passages.append(
                {
                    "chunkId": chunk.get("chunk_id") or f"{source_file}:{source_location}",
                    "sourceFile": source_file,
                    "sourceLocation": source_location,
                    "pageStart": chunk.get("page_start"),
                    "pageEnd": chunk.get("page_end"),
                    "text": chunk.get("text") or "",
                    "relatedNodeIds": [node["id"]],
                }
            )
            return


def get_node_service() -> NodeService:
    """FastAPI dependency for the node service."""
    return NodeService()