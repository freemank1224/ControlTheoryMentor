"""Tests for the Graphify worker orchestration layer."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from worker.graphify_wrapper import GraphifyConfigurationError, GraphifyProcessor, LLMConfig


def test_llm_config_requires_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRAPHIFY_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GRAPHIFY_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(GraphifyConfigurationError):
        LLMConfig.from_env()


def test_merge_extractions_deduplicates_nodes_and_edges() -> None:
    processor = GraphifyProcessor(neo4j_uri="", neo4j_user="", neo4j_password="")
    merged = processor._merge_extractions(
        {
            "nodes": [{"id": "n1", "label": "A", "file_type": "paper", "source_file": "raw/a.pdf"}],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "relation": "mentions",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": "raw/a.pdf",
                    "source_location": "P1",
                    "weight": 1.0,
                }
            ],
            "hyperedges": [],
            "input_tokens": 10,
            "output_tokens": 20,
        },
        {
            "nodes": [
                {"id": "n1", "label": "A updated", "file_type": "paper", "source_file": "raw/a.pdf"},
                {"id": "n2", "label": "B", "file_type": "paper", "source_file": "raw/a.pdf"},
            ],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "relation": "mentions",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": "raw/a.pdf",
                    "source_location": "P1",
                    "weight": 1.0,
                }
            ],
            "hyperedges": [{"id": "h1", "label": "Group", "nodes": ["n1", "n2", "n3"]}],
            "input_tokens": 5,
            "output_tokens": 15,
        },
    )

    assert len(merged["nodes"]) == 2
    assert len(merged["edges"]) == 1
    assert merged["input_tokens"] == 15
    assert merged["output_tokens"] == 35
    assert next(node for node in merged["nodes"] if node["id"] == "n1")["label"] == "A updated"


def test_run_semantic_completion_supports_anthropic_compatible_endpoints() -> None:
    processor = GraphifyProcessor(
        neo4j_uri="",
        neo4j_user="",
        neo4j_password="",
        llm_config=LLMConfig(
            api_key="test-key",
            model="MiniMax-M2.7",
            base_url="https://api.minimaxi.com/anthropic",
            timeout_seconds=30,
            max_chunk_chars=1000,
            max_output_tokens=500,
        ),
    )

    class FakeHttpxClient:
        def post(self, url: str, headers: dict[str, str], json: dict[str, object]):
            assert url == "https://api.minimaxi.com/anthropic/v1/messages"
            assert headers["x-api-key"] == "test-key"
            assert json["model"] == "MiniMax-M2.7"
            assert json["thinking"] == {"type": "disabled"}
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "content": [
                        {
                            "type": "text",
                            "text": json_module.dumps(
                                {
                                    "nodes": [
                                        {
                                            "id": "paper_1",
                                            "label": "Control System",
                                            "file_type": "paper",
                                        },
                                        {
                                            "id": "concept_1",
                                            "label": "State Space",
                                            "file_type": "paper",
                                        },
                                    ],
                                    "edges": [
                                        {
                                            "source": "paper_1",
                                            "target": "concept_1",
                                            "relation": "mentions",
                                            "confidence": "EXTRACTED",
                                            "confidence_score": 1.0,
                                        }
                                    ],
                                    "hyperedges": [],
                                }
                            ),
                        }
                    ],
                    "usage": {"input_tokens": 12, "output_tokens": 8},
                },
            )

    json_module = json
    processor._client = FakeHttpxClient()

    extraction = processor._run_semantic_completion(
        "Return JSON",
        source_file="raw/sample.pdf",
        file_type="paper",
        source_location="P1",
        node_metadata={},
    )

    assert extraction["input_tokens"] == 12
    assert extraction["output_tokens"] == 8
    assert len(extraction["nodes"]) == 2
    assert extraction["edges"][0]["relation"] == "mentions"


def test_run_semantic_completion_repairs_anthropic_thinking_only_response() -> None:
    processor = GraphifyProcessor(
        neo4j_uri="",
        neo4j_user="",
        neo4j_password="",
        llm_config=LLMConfig(
            api_key="test-key",
            model="MiniMax-M2.7",
            base_url="https://api.minimaxi.com/anthropic",
            timeout_seconds=30,
            max_chunk_chars=1000,
            max_output_tokens=500,
        ),
    )

    responses = [
        {
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Nodes: Control System, State Space. Edge: Control System mentions State Space.",
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "nodes": [
                                {"id": "paper_1", "label": "Control System", "file_type": "paper"},
                                {"id": "concept_1", "label": "State Space", "file_type": "paper"},
                            ],
                            "edges": [
                                {
                                    "source": "paper_1",
                                    "target": "concept_1",
                                    "relation": "mentions",
                                    "confidence": "EXTRACTED",
                                    "confidence_score": 1.0,
                                }
                            ],
                            "hyperedges": [],
                        }
                    ),
                }
            ],
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
    ]

    class FakeHttpxClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]):
            self.calls.append(json)
            payload = responses[len(self.calls) - 1]
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda payload=payload: payload,
            )

    fake_client = FakeHttpxClient()
    processor._client = fake_client

    extraction = processor._run_semantic_completion(
        "Return JSON",
        source_file="raw/sample.pdf",
        file_type="paper",
        source_location="P1",
        node_metadata={},
    )

    assert len(fake_client.calls) == 2
    assert "previous reply did not include a final JSON text block" in fake_client.calls[1]["messages"][0]["content"][0]["text"]
    assert extraction["input_tokens"] == 15
    assert extraction["output_tokens"] == 27
    assert len(extraction["nodes"]) == 2


def test_run_semantic_completion_repairs_invalid_json_response() -> None:
    processor = GraphifyProcessor(
        neo4j_uri="",
        neo4j_user="",
        neo4j_password="",
        llm_config=LLMConfig(
            api_key="test-key",
            model="test-model",
            base_url=None,
            timeout_seconds=30,
            max_chunk_chars=1000,
            max_output_tokens=500,
        ),
    )

    responses = [
        '{"nodes":[{"id":"paper_1","label":"Control System","file_type":"paper"}],"edges":[}',
        json.dumps(
            {
                "nodes": [
                    {"id": "paper_1", "label": "Control System", "file_type": "paper"},
                    {"id": "concept_1", "label": "State Space", "file_type": "paper"},
                ],
                "edges": [
                    {
                        "source": "paper_1",
                        "target": "concept_1",
                        "relation": "mentions",
                        "confidence": "EXTRACTED",
                        "confidence_score": 1.0,
                    }
                ],
                "hyperedges": [],
            }
        ),
    ]

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            self.calls.append(kwargs)
            content = responses[len(self.calls) - 1]
            return SimpleNamespace(
                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=13),
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            )

    fake_client = FakeOpenAIClient()
    processor._client = fake_client

    extraction = processor._run_semantic_completion(
        "Return JSON",
        source_file="raw/sample.pdf",
        file_type="paper",
        source_location="P1",
        node_metadata={},
    )

    assert len(fake_client.calls) == 2
    assert extraction["edges"][0]["relation"] == "mentions"


def test_run_semantic_completion_repairs_common_json_locally() -> None:
        processor = GraphifyProcessor(
                neo4j_uri="",
                neo4j_user="",
                neo4j_password="",
                llm_config=LLMConfig(
                        api_key="test-key",
                        model="test-model",
                        base_url=None,
                        timeout_seconds=30,
                        max_chunk_chars=1000,
                        max_output_tokens=500,
                ),
        )

        malformed_response = """```json
        {
            "nodes": [
                {"id": "paper_1", "label": "Control System", "file_type": "paper"},
                {"id": "concept_1", "label": "State Space", "file_type": "paper"}
            ],
            "edges": [
                {
                    "source": "paper_1",
                    "target": "concept_1",
                    "relation": "mentions",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                }
            ],
            "hyperedges": []
        """

        class FakeOpenAIClient:
                def __init__(self) -> None:
                        self.calls: list[dict[str, object]] = []
                        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

                def create(self, **kwargs):
                        self.calls.append(kwargs)
                        return SimpleNamespace(
                                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=13),
                                choices=[SimpleNamespace(message=SimpleNamespace(content=malformed_response))],
                        )

        fake_client = FakeOpenAIClient()
        processor._client = fake_client

        extraction = processor._run_semantic_completion(
                "Return JSON",
                source_file="raw/sample.pdf",
                file_type="paper",
                source_location="P1",
                node_metadata={},
        )

        assert len(fake_client.calls) == 1
        assert len(extraction["nodes"]) == 2
        assert extraction["edges"][0]["relation"] == "mentions"


def test_process_pdf_builds_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    processor = GraphifyProcessor(
        neo4j_uri="",
        neo4j_user="",
        neo4j_password="",
        artifacts_root=str(tmp_path / "artifacts"),
        llm_config=LLMConfig(
            api_key="test-key",
            model="test-model",
            base_url=None,
            timeout_seconds=30,
            max_chunk_chars=1000,
            max_output_tokens=500,
        ),
    )

    def fake_detect(graph_root: Path) -> dict[str, object]:
        staged = graph_root / "raw" / "sample.pdf"
        return {
            "files": {"code": [], "document": [], "paper": [str(staged)], "image": []},
            "total_files": 1,
            "total_words": 120,
        }

    monkeypatch.setattr("worker.graphify_wrapper.detect", fake_detect)
    monkeypatch.setattr(
        processor,
        "_extract_code_files",
        lambda detection_result: {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0},
    )
    monkeypatch.setattr(
        processor,
        "_extract_semantic_files",
        lambda detection_result, graph_root, progress: (
            {
                "nodes": [
                    {"id": "paper_1", "label": "sample", "file_type": "paper", "source_file": "raw/sample.pdf", "source_location": "P1"},
                    {"id": "concept_1", "label": "State Space", "file_type": "paper", "source_file": "raw/sample.pdf", "source_location": "P1"},
                ],
                "edges": [
                    {
                        "source": "paper_1",
                        "target": "concept_1",
                        "relation": "mentions",
                        "confidence": "EXTRACTED",
                        "confidence_score": 1.0,
                        "source_file": "raw/sample.pdf",
                        "source_location": "P1",
                        "weight": 1.0,
                    }
                ],
                "hyperedges": [],
                "input_tokens": 11,
                "output_tokens": 7,
            },
            {"hits": 0, "misses": 1},
        ),
    )
    monkeypatch.setattr("worker.graphify_wrapper.cluster", lambda graph: {0: ["paper_1", "concept_1"]})
    monkeypatch.setattr("worker.graphify_wrapper.score_all", lambda graph, communities: {0: 0.8})
    monkeypatch.setattr("worker.graphify_wrapper.god_nodes", lambda graph: [{"label": "sample", "degree": 1}])
    monkeypatch.setattr("worker.graphify_wrapper.surprising_connections", lambda graph, communities: [])
    monkeypatch.setattr("worker.graphify_wrapper.suggest_questions", lambda graph, communities, labels: [])
    monkeypatch.setattr(
        "worker.graphify_wrapper.generate",
        lambda graph, communities, cohesion, labels, god_nodes, surprises, detection, token_cost, root, suggested_questions=None: "# report\n",
    )
    monkeypatch.setattr("worker.graphify_wrapper.save_manifest", lambda files, path: Path(path).write_text(json.dumps(files), encoding="utf-8"))

    result = processor.process_pdf(str(pdf_path), "graph-task-1")

    assert result["nodes_count"] == 2
    assert result["edges_count"] == 1
    assert result["input_tokens"] == 11
    assert result["output_tokens"] == 7
    assert Path(result["graph_json_path"]).exists()
    assert Path(result["report_path"]).exists()
