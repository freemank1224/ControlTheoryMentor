"""Upstream Graphify-aligned orchestration for worker PDF processing."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import httpx
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Iterable

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cache import check_semantic_cache, save_semantic_cache
from graphify.cluster import cluster, score_all
from graphify.detect import detect, save_manifest
from graphify.export import push_to_neo4j, to_cypher, to_html, to_json
from graphify.extract import extract as extract_code
from graphify.report import generate
from graphify.validate import VALID_CONFIDENCES, VALID_FILE_TYPES, assert_valid
from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError, RateLimitError
from openai.types.chat import ChatCompletion
from pypdf import PdfReader

ProgressCallback = Callable[[int, str], None]

JSON_REPAIR_TEMPLATE = """
The previous response was invalid for Graphify extraction.
Return only valid JSON with keys nodes, edges, hyperedges, input_tokens, output_tokens.
Validation problem:
{error}
""".strip()

SEMANTIC_EXTRACTION_SYSTEM_PROMPT = """
You are Graphify semantic extraction.

Read the provided chunk and return only a JSON object with keys:
- nodes
- edges
- hyperedges
- input_tokens
- output_tokens

Rules:
- EXTRACTED means the relationship is explicit in the chunk.
- INFERRED means the relationship is a reasonable semantic inference.
- AMBIGUOUS means the relationship is uncertain and needs review.
- Use only meaningful concepts, entities, formulas, methods, components, rationale notes, or design abstractions.
- Never emit stopwords, section numbers, or generic filler terms.
- Do not create a file node; the caller adds it separately.
- Keep the graph concise: prefer up to 20 nodes, 40 edges, and 3 hyperedges for one chunk.
- Every edge must include confidence_score.
- EXTRACTED edges must use confidence_score 1.0.
- INFERRED edges should usually use 0.6-0.9.
- AMBIGUOUS edges should use 0.1-0.3.

Allowed file_type values:
- code
- document
- paper
- image
- rationale

Suggested relations:
- mentions
- discusses
- cites
- references
- conceptually_related_to
- semantically_similar_to
- shares_data_with
- rationale_for
- implements
- calls
- contains

Output JSON only. No markdown fences. No commentary.
""".strip()


class GraphifyProcessingError(RuntimeError):
    """Base error for Graphify worker orchestration failures."""


class GraphifyConfigurationError(GraphifyProcessingError):
    """Raised when the runtime is missing required provider configuration."""


class GraphifySemanticExtractionError(GraphifyProcessingError):
    """Raised when the model cannot return a valid Graphify extraction."""


class GraphifyTransientError(GraphifyProcessingError):
    """Raised for retryable provider failures."""


@dataclass(frozen=True)
class TextChunk:
    source_location: str
    text: str


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    base_url: str | None
    timeout_seconds: float
    max_chunk_chars: int
    max_output_tokens: int

    @classmethod
    def from_env(cls) -> LLMConfig:
        api_key = os.getenv("GRAPHIFY_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("GRAPHIFY_LLM_MODEL") or os.getenv("OPENAI_MODEL")
        base_url = os.getenv("GRAPHIFY_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        timeout_seconds = float(os.getenv("GRAPHIFY_LLM_TIMEOUT_SECONDS", "120"))
        max_chunk_chars = int(os.getenv("GRAPHIFY_LLM_MAX_CHUNK_CHARS", "50000"))
        max_output_tokens = int(os.getenv("GRAPHIFY_LLM_MAX_OUTPUT_TOKENS", "4000"))

        if not api_key:
            raise GraphifyConfigurationError(
                "Semantic Graphify extraction requires GRAPHIFY_LLM_API_KEY or OPENAI_API_KEY."
            )
        if not model:
            raise GraphifyConfigurationError(
                "Semantic Graphify extraction requires GRAPHIFY_LLM_MODEL or OPENAI_MODEL."
            )

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_chunk_chars=max_chunk_chars,
            max_output_tokens=max_output_tokens,
        )


def _graphify_version() -> str:
    try:
        return version("graphifyy")
    except PackageNotFoundError:
        return "unknown"


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "::".join(part.strip() for part in parts if part and part.strip())
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower() or "node"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}, text

    end_marker = text.find("\n---", 4)
    if end_marker == -1:
        return {}, text

    raw_meta = text[4:end_marker].splitlines()
    metadata: dict[str, str] = {}
    for line in raw_meta:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, text[end_marker + 4 :].lstrip()


class GraphifyProcessor:
    """Run the upstream Graphify pipeline with model-backed semantic extraction."""

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        artifacts_root: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.artifacts_root = Path(
            artifacts_root or os.getenv("GRAPH_ARTIFACTS_PATH", "./graph_data")
        )
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.llm_config = llm_config
        self._client: Any | None = None

    def process_pdf(
        self,
        pdf_path: str,
        graph_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        progress = progress_callback or (lambda _percent, _message: None)
        source_pdf = Path(pdf_path)
        if not source_pdf.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        graph_root = self.artifacts_root / graph_id
        if graph_root.exists():
            shutil.rmtree(graph_root)

        raw_dir = graph_root / "raw"
        output_dir = graph_root / "graphify-out"
        raw_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        progress(10, "Staging PDF into Graphify corpus...")
        staged_pdf = raw_dir / source_pdf.name
        shutil.copy2(source_pdf, staged_pdf)

        progress(20, "Running Graphify detect stage...")
        detection_result = detect(graph_root)
        (output_dir / ".graphify_detect.json").write_text(
            json.dumps(detection_result, indent=2),
            encoding="utf-8",
        )

        progress(30, "Running Graphify AST extraction stage...")
        ast_extraction = self._extract_code_files(detection_result)
        (output_dir / ".graphify_ast.json").write_text(
            json.dumps(ast_extraction, indent=2),
            encoding="utf-8",
        )

        progress(40, "Running Graphify semantic extraction stage...")
        semantic_extraction, cache_stats = self._extract_semantic_files(
            detection_result,
            graph_root,
            progress,
        )
        (output_dir / ".graphify_semantic.json").write_text(
            json.dumps(semantic_extraction, indent=2),
            encoding="utf-8",
        )

        merged_extraction = self._merge_extractions(ast_extraction, semantic_extraction)
        assert_valid(merged_extraction)
        (output_dir / ".graphify_extract.json").write_text(
            json.dumps(merged_extraction, indent=2),
            encoding="utf-8",
        )

        progress(65, "Running Graphify build and cluster stages...")
        graph = build_from_json(merged_extraction)
        communities = cluster(graph)
        cohesion_scores = score_all(graph, communities)
        community_labels = self._label_communities(graph, communities)
        top_god_nodes = god_nodes(graph)
        surprises = surprising_connections(graph, communities)
        questions = suggest_questions(graph, communities, community_labels)

        progress(80, "Generating Graphify report and exports...")
        token_cost = {
            "input": merged_extraction.get("input_tokens", 0),
            "output": merged_extraction.get("output_tokens", 0),
        }
        report = generate(
            graph,
            communities,
            cohesion_scores,
            community_labels,
            top_god_nodes,
            surprises,
            detection_result,
            token_cost,
            str(graph_root.name),
            suggested_questions=questions,
        )
        report_path = output_dir / "GRAPH_REPORT.md"
        graph_json_path = output_dir / "graph.json"
        cypher_path = output_dir / "cypher.txt"
        html_path = output_dir / "graph.html"
        manifest_path = output_dir / "manifest.json"

        report_path.write_text(report, encoding="utf-8")
        to_json(graph, communities, str(graph_json_path))
        to_cypher(graph, str(cypher_path))

        try:
            to_html(graph, communities, str(html_path), community_labels=community_labels)
        except ValueError:
            pass

        save_manifest(detection_result.get("files", {}), str(manifest_path))

        neo4j_summary = None
        if self.neo4j_uri and self.neo4j_user and self.neo4j_password:
            progress(90, "Pushing Graphify graph to Neo4j...")
            try:
                neo4j_summary = push_to_neo4j(
                    graph,
                    self.neo4j_uri,
                    self.neo4j_user,
                    self.neo4j_password,
                    communities,
                )
            except Exception:
                neo4j_summary = None

        progress(100, "Graphify processing completed.")
        return {
            "graph_id": graph_id,
            "graph_root": str(graph_root),
            "graph_json_path": str(graph_json_path),
            "report_path": str(report_path),
            "nodes_count": graph.number_of_nodes(),
            "edges_count": graph.number_of_edges(),
            "communities_count": len(communities),
            "files_processed": detection_result.get("total_files", 0),
            "total_words": detection_result.get("total_words", 0),
            "input_tokens": token_cost["input"],
            "output_tokens": token_cost["output"],
            "semantic_cache_hits": cache_stats["hits"],
            "semantic_cache_misses": cache_stats["misses"],
            "graphify_version": _graphify_version(),
            "neo4j": neo4j_summary,
        }

    def _extract_code_files(self, detection_result: dict[str, Any]) -> dict[str, Any]:
        code_files = [Path(path) for path in detection_result.get("files", {}).get("code", [])]
        if not code_files:
            return self._empty_extraction()

        result = extract_code(code_files)
        return {
            "nodes": result.get("nodes", []),
            "edges": result.get("edges", []),
            "hyperedges": result.get("hyperedges", []),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
        }

    def _extract_semantic_files(
        self,
        detection_result: dict[str, Any],
        graph_root: Path,
        progress: ProgressCallback,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        files = detection_result.get("files", {})
        semantic_paths = [
            file_path
            for category in ("document", "paper", "image")
            for file_path in files.get(category, [])
        ]

        if not semantic_paths:
            return self._empty_extraction(), {"hits": 0, "misses": 0}

        cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(
            semantic_paths,
            root=graph_root,
        )
        cached_extraction = {
            "nodes": cached_nodes,
            "edges": cached_edges,
            "hyperedges": cached_hyperedges,
            "input_tokens": 0,
            "output_tokens": 0,
        }

        if not uncached:
            return cached_extraction, {"hits": len(semantic_paths), "misses": 0}

        self._require_llm_config()
        extracted: list[dict[str, Any]] = []
        total_uncached = len(uncached)
        for index, file_path in enumerate(uncached, start=1):
            base_percent = 40
            progress_span = 25
            percent = base_percent + int(progress_span * index / max(total_uncached, 1))
            progress(percent, f"Semantic extraction {index}/{total_uncached}: {Path(file_path).name}")
            extracted.append(self._extract_semantic_file(Path(file_path), graph_root))

        new_extraction = self._merge_extractions(*extracted)
        save_semantic_cache(
            new_extraction.get("nodes", []),
            new_extraction.get("edges", []),
            new_extraction.get("hyperedges", []),
            root=graph_root,
        )

        merged = self._merge_extractions(cached_extraction, new_extraction)
        return merged, {"hits": len(semantic_paths) - len(uncached), "misses": len(uncached)}

    def _extract_semantic_file(self, file_path: Path, graph_root: Path) -> dict[str, Any]:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_paper(file_path, graph_root)
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            return self._extract_image(file_path, graph_root)
        return self._extract_document(file_path, graph_root)

    def _extract_paper(self, pdf_path: Path, graph_root: Path) -> dict[str, Any]:
        pages = self._read_pdf_pages(pdf_path)
        if not pages:
            raise ValueError(f"No extractable text found in {pdf_path.name}")

        source_file = pdf_path.relative_to(graph_root).as_posix()
        chunks = self._chunk_pages(pages, self._require_llm_config().max_chunk_chars)
        partials = [
            self._extract_text_chunk(
                file_label=pdf_path.stem,
                file_type="paper",
                source_file=source_file,
                chunk=chunk,
            )
            for chunk in chunks
        ]
        extraction = self._merge_extractions(*partials)
        extraction = self._attach_file_node(
            extraction,
            file_label=pdf_path.stem,
            file_type="paper",
            source_file=source_file,
            source_location=chunks[0].source_location,
        )
        assert_valid(extraction)
        return extraction

    def _extract_document(self, doc_path: Path, graph_root: Path) -> dict[str, Any]:
        metadata, text = _read_frontmatter(doc_path)
        source_file = doc_path.relative_to(graph_root).as_posix()
        chunks = self._chunk_text(text, self._require_llm_config().max_chunk_chars)
        if not chunks:
            raise ValueError(f"No extractable text found in {doc_path.name}")

        partials = [
            self._extract_text_chunk(
                file_label=doc_path.stem,
                file_type="document",
                source_file=source_file,
                chunk=chunk,
                node_metadata=metadata,
            )
            for chunk in chunks
        ]
        extraction = self._merge_extractions(*partials)
        extraction = self._attach_file_node(
            extraction,
            file_label=doc_path.stem,
            file_type="document",
            source_file=source_file,
            source_location=chunks[0].source_location,
            node_metadata=metadata,
        )
        assert_valid(extraction)
        return extraction

    def _extract_image(self, image_path: Path, graph_root: Path) -> dict[str, Any]:
        source_file = image_path.relative_to(graph_root).as_posix()
        mime_type, _ = mimetypes.guess_type(image_path.name)
        if mime_type is None:
            mime_type = "image/png"

        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = self._build_chunk_prompt(
            file_label=image_path.stem,
            file_type="image",
            source_file=source_file,
            source_location="image",
            text="Describe the image semantically. Extract components, concepts, claims, and relationships.",
        )
        extraction = self._run_semantic_completion(
            prompt,
            source_file=source_file,
            file_type="image",
            source_location="image",
            node_metadata={},
            image_payload={
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            },
        )
        extraction = self._attach_file_node(
            extraction,
            file_label=image_path.stem,
            file_type="image",
            source_file=source_file,
            source_location="image",
        )
        assert_valid(extraction)
        return extraction

    def _extract_text_chunk(
        self,
        *,
        file_label: str,
        file_type: str,
        source_file: str,
        chunk: TextChunk,
        node_metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        prompt = self._build_chunk_prompt(
            file_label=file_label,
            file_type=file_type,
            source_file=source_file,
            source_location=chunk.source_location,
            text=chunk.text,
        )
        return self._run_semantic_completion(
            prompt,
            source_file=source_file,
            file_type=file_type,
            source_location=chunk.source_location,
            node_metadata=node_metadata or {},
        )

    def _run_semantic_completion(
        self,
        prompt: str,
        *,
        source_file: str,
        file_type: str,
        source_location: str,
        node_metadata: dict[str, str],
        image_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = self._require_llm_config()
        attempts = 2
        total_input_tokens = 0
        total_output_tokens = 0
        repair_error: str | None = None

        for _attempt in range(attempts):
            try:
                prompt_with_repair = (
                    prompt
                    if repair_error is None
                    else f"{prompt}\n\n{JSON_REPAIR_TEMPLATE.format(error=repair_error)}"
                )
                content, input_tokens, output_tokens = self._request_semantic_completion(
                    config,
                    prompt_with_repair,
                    image_payload=image_payload,
                )
            except GraphifyProcessingError:
                raise

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            try:
                payload = self._parse_json_payload(content)
                extraction = self._normalize_semantic_payload(
                    payload,
                    source_file=source_file,
                    file_type=file_type,
                    source_location=source_location,
                    node_metadata=node_metadata,
                )
                extraction["input_tokens"] = total_input_tokens
                extraction["output_tokens"] = total_output_tokens
                assert_valid(extraction)
                return extraction
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                repair_error = str(exc)

        raise GraphifySemanticExtractionError(
            f"Model could not return valid Graphify extraction for {source_file}: {repair_error}"
        )

    def _request_semantic_completion(
        self,
        config: LLMConfig,
        prompt: str,
        *,
        image_payload: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        if self._is_anthropic_compatible(config):
            return self._request_anthropic_completion(config, prompt, image_payload=image_payload)
        return self._request_openai_completion(config, prompt, image_payload=image_payload)

    def _request_openai_completion(
        self,
        config: LLMConfig,
        prompt: str,
        *,
        image_payload: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        client = self._client
        if client is None or not hasattr(client, "chat"):
            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
            )
            self._client = client

        try:
            user_content: Any
            if image_payload:
                user_content = [
                    {"type": "text", "text": prompt},
                    image_payload,
                ]
            else:
                user_content = prompt

            response: ChatCompletion = client.chat.completions.create(
                model=config.model,
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=config.max_output_tokens,
                messages=[
                    {"role": "system", "content": SEMANTIC_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            raise GraphifyTransientError(f"Transient Graphify provider failure: {exc}") from exc
        except OpenAIError as exc:
            raise GraphifySemanticExtractionError(f"Graphify provider request failed: {exc}") from exc

        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        content = response.choices[0].message.content or "{}"
        return content, input_tokens, output_tokens

    def _request_anthropic_completion(
        self,
        config: LLMConfig,
        prompt: str,
        *,
        image_payload: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        client = self._client
        if client is None or hasattr(client, "chat") or not hasattr(client, "post"):
            client = httpx.Client(timeout=config.timeout_seconds)
            self._client = client

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "x-api-key": config.api_key,
            "anthropic-version": os.getenv("GRAPHIFY_LLM_ANTHROPIC_VERSION", "2023-06-01"),
            "content-type": "application/json",
        }
        body = {
            "model": config.model,
            "temperature": 0,
            "max_tokens": config.max_output_tokens,
            "system": SEMANTIC_EXTRACTION_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": self._build_anthropic_content(prompt, image_payload),
                }
            ],
        }
        thinking = self._anthropic_thinking_config()
        if thinking is not None:
            body["thinking"] = thinking
        payload, input_tokens, output_tokens = self._post_anthropic_request(
            client,
            config,
            headers,
            body,
        )

        content = self._extract_anthropic_text(payload, raise_if_missing=False)
        if content is not None:
            return content, input_tokens, output_tokens

        thinking_text = self._extract_anthropic_thinking(payload)
        if not thinking_text:
            raise GraphifySemanticExtractionError(
                f"Graphify provider returned no text content: {json.dumps(payload)}"
            )

        repair_body = {
            "model": config.model,
            "temperature": 0,
            "max_tokens": max(config.max_output_tokens, 1600),
            "system": SEMANTIC_EXTRACTION_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._build_anthropic_repair_prompt(prompt, thinking_text),
                        }
                    ],
                }
            ],
        }
        if thinking is not None:
            repair_body["thinking"] = thinking

        repair_payload, repair_input_tokens, repair_output_tokens = self._post_anthropic_request(
            client,
            config,
            headers,
            repair_body,
        )
        repair_content = self._extract_anthropic_text(repair_payload)
        return (
            repair_content,
            input_tokens + repair_input_tokens,
            output_tokens + repair_output_tokens,
        )

    def _post_anthropic_request(
        self,
        client: Any,
        config: LLMConfig,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[dict[str, Any], int, int]:
        try:
            response = client.post(
                self._anthropic_messages_url(config),
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise GraphifyTransientError(f"Transient Graphify provider failure: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {408, 409, 429} or status_code >= 500:
                raise GraphifyTransientError(f"Transient Graphify provider failure: {exc}") from exc
            raise GraphifySemanticExtractionError(
                f"Graphify provider request failed: {exc.response.text}"
            ) from exc

        payload = response.json()
        usage = payload.get("usage", {})
        return (
            payload,
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
        )

    def _build_anthropic_content(
        self,
        prompt: str,
        image_payload: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        blocks = [{"type": "text", "text": prompt}]
        if image_payload:
            image_url = image_payload.get("image_url", {}).get("url", "")
            match = re.match(r"data:(?P<media_type>[^;]+);base64,(?P<data>.+)", image_url)
            if match:
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": match.group("media_type"),
                            "data": match.group("data"),
                        },
                    }
                )
        return blocks

    def _anthropic_messages_url(self, config: LLMConfig) -> str:
        base_url = (config.base_url or "https://api.anthropic.com").rstrip("/")
        if base_url.endswith("/v1/messages"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/messages"
        return f"{base_url}/v1/messages"

    def _extract_anthropic_text(self, payload: dict[str, Any], raise_if_missing: bool = True) -> str | None:
        text_parts = [
            block.get("text", "")
            for block in payload.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if not text_parts:
            if raise_if_missing:
                raise GraphifySemanticExtractionError(
                    f"Graphify provider returned no text content: {json.dumps(payload)}"
                )
            return None
        return "\n".join(part for part in text_parts if part)

    def _extract_anthropic_thinking(self, payload: dict[str, Any]) -> str:
        thinking_parts = [
            block.get("thinking", "")
            for block in payload.get("content", [])
            if isinstance(block, dict) and block.get("type") == "thinking"
        ]
        return "\n".join(part for part in thinking_parts if part).strip()

    def _is_anthropic_compatible(self, config: LLMConfig) -> bool:
        base_url = (config.base_url or "").lower()
        return "/anthropic" in base_url

    def _anthropic_thinking_config(self) -> dict[str, str] | None:
        value = os.getenv("GRAPHIFY_LLM_ANTHROPIC_THINKING_DISABLED", "true").strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return {"type": "disabled"}
        return None

    def _build_anthropic_repair_prompt(self, original_prompt: str, thinking_text: str) -> str:
        return (
            "Your previous reply did not include a final JSON text block. "
            "Convert the draft extraction notes below into one valid JSON object with keys "
            "nodes, edges, hyperedges, input_tokens, output_tokens. "
            "Return JSON only. Do not include reasoning.\n\n"
            f"Original extraction prompt:\n{original_prompt}\n\n"
            "Draft extraction notes:\n<<<\n"
            f"{thinking_text}\n"
            ">>>"
        )

    def _build_chunk_prompt(
        self,
        *,
        file_label: str,
        file_type: str,
        source_file: str,
        source_location: str,
        text: str,
    ) -> str:
        file_id_prefix = _slug(Path(source_file).stem)
        return (
            f"File label: {file_label}\n"
            f"File type: {file_type}\n"
            f"Source file: {source_file}\n"
            f"Source location: {source_location}\n"
            f"Node ID prefix: {file_id_prefix}\n\n"
            "Return only nodes and edges supported by the provided chunk.\n"
            "Chunk content:\n"
            "<<<\n"
            f"{text}\n"
            ">>>"
        )

    def _normalize_semantic_payload(
        self,
        payload: dict[str, Any],
        *,
        source_file: str,
        file_type: str,
        source_location: str,
        node_metadata: dict[str, str],
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        for raw_node in payload.get("nodes", []):
            if not isinstance(raw_node, dict):
                continue
            label = _normalize_whitespace(str(raw_node.get("label", "")))
            if not label:
                continue
            node_type = str(raw_node.get("file_type") or file_type)
            if node_type not in VALID_FILE_TYPES:
                node_type = file_type
            node_id = _normalize_whitespace(str(raw_node.get("id") or _stable_id(_slug(node_type), source_file, label)))
            if not node_id:
                continue

            normalized = {
                "id": node_id,
                "label": label,
                "file_type": node_type,
                "source_file": source_file,
                "source_location": raw_node.get("source_location") or source_location,
            }
            for key in ("source_url", "captured_at", "author", "contributor"):
                value = raw_node.get(key) or node_metadata.get(key)
                if value:
                    normalized[key] = value
            nodes.append(normalized)

        node_ids = {node["id"] for node in nodes}
        edges: list[dict[str, Any]] = []
        for raw_edge in payload.get("edges", []) or payload.get("links", []):
            if not isinstance(raw_edge, dict):
                continue
            source = _normalize_whitespace(str(raw_edge.get("source") or raw_edge.get("from") or ""))
            target = _normalize_whitespace(str(raw_edge.get("target") or raw_edge.get("to") or ""))
            relation = _normalize_whitespace(str(raw_edge.get("relation", "")))
            confidence = str(raw_edge.get("confidence") or "INFERRED").upper()
            if not source or not target or not relation:
                continue
            if confidence not in VALID_CONFIDENCES:
                confidence = "INFERRED"

            if source not in node_ids or target not in node_ids:
                continue

            confidence_score = raw_edge.get("confidence_score")
            if confidence_score is None:
                confidence_score = 1.0 if confidence == "EXTRACTED" else (0.7 if confidence == "INFERRED" else 0.2)

            weight = raw_edge.get("weight")
            if weight is None:
                weight = 1.0

            edges.append({
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": confidence,
                "confidence_score": float(confidence_score),
                "source_file": source_file,
                "source_location": raw_edge.get("source_location") or source_location,
                "weight": float(weight),
            })

        hyperedges: list[dict[str, Any]] = []
        for raw_hyperedge in payload.get("hyperedges", []):
            if not isinstance(raw_hyperedge, dict):
                continue
            nodes_list = [node_id for node_id in raw_hyperedge.get("nodes", []) if node_id in node_ids]
            if len(nodes_list) < 3:
                continue
            hyperedges.append({
                "id": raw_hyperedge.get("id") or _stable_id("hyperedge", source_file, raw_hyperedge.get("label", "group")),
                "label": raw_hyperedge.get("label") or "Group",
                "nodes": nodes_list,
                "relation": raw_hyperedge.get("relation") or "participate_in",
                "confidence": raw_hyperedge.get("confidence") or "INFERRED",
                "confidence_score": float(raw_hyperedge.get("confidence_score") or 0.7),
                "source_file": source_file,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "hyperedges": hyperedges,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _attach_file_node(
        self,
        extraction: dict[str, Any],
        *,
        file_label: str,
        file_type: str,
        source_file: str,
        source_location: str,
        node_metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        metadata = node_metadata or {}
        file_node_id = _stable_id(file_type, source_file)
        file_node = {
            "id": file_node_id,
            "label": file_label,
            "file_type": file_type,
            "source_file": source_file,
            "source_location": source_location,
        }
        for key in ("source_url", "captured_at", "author", "contributor"):
            value = metadata.get(key)
            if value:
                file_node[key] = value

        combined_nodes = [file_node, *extraction.get("nodes", [])]
        combined_edges = list(extraction.get("edges", []))
        existing_keys = {
            (edge["source"], edge["target"], edge["relation"], edge.get("source_location"))
            for edge in combined_edges
        }
        for node in extraction.get("nodes", []):
            if node["id"] == file_node_id:
                continue
            relation = "mentions"
            key = (file_node_id, node["id"], relation, node.get("source_location"))
            if key in existing_keys:
                continue
            combined_edges.append({
                "source": file_node_id,
                "target": node["id"],
                "relation": relation,
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "source_file": source_file,
                "source_location": node.get("source_location") or source_location,
                "weight": 1.0,
            })

        return self._merge_extractions(
            {
                "nodes": combined_nodes,
                "edges": combined_edges,
                "hyperedges": extraction.get("hyperedges", []),
                "input_tokens": extraction.get("input_tokens", 0),
                "output_tokens": extraction.get("output_tokens", 0),
            }
        )

    def _merge_extractions(self, *extractions: dict[str, Any]) -> dict[str, Any]:
        merged_nodes: dict[str, dict[str, Any]] = {}
        merged_edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        merged_hyperedges: dict[str, dict[str, Any]] = {}
        input_tokens = 0
        output_tokens = 0

        for extraction in extractions:
            if not extraction:
                continue
            input_tokens += extraction.get("input_tokens", 0)
            output_tokens += extraction.get("output_tokens", 0)

            for node in extraction.get("nodes", []):
                if not isinstance(node, dict) or "id" not in node:
                    continue
                merged_nodes[node["id"]] = node

            for edge in extraction.get("edges", []):
                if not isinstance(edge, dict):
                    continue
                key = (
                    edge.get("source", ""),
                    edge.get("target", ""),
                    edge.get("relation", ""),
                    edge.get("source_file", ""),
                    edge.get("source_location", ""),
                )
                if not all(key[:3]):
                    continue
                merged_edges[key] = edge

            for hyperedge in extraction.get("hyperedges", []):
                if not isinstance(hyperedge, dict):
                    continue
                hyperedge_id = str(hyperedge.get("id") or _stable_id("hyperedge", hyperedge.get("label", "group")))
                merged_hyperedges[hyperedge_id] = {**hyperedge, "id": hyperedge_id}

        return {
            "nodes": list(merged_nodes.values()),
            "edges": list(merged_edges.values()),
            "hyperedges": list(merged_hyperedges.values()),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def _parse_json_payload(self, content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise json.JSONDecodeError("No JSON object found", stripped, 0)
        return json.loads(stripped[start : end + 1])

    def _require_llm_config(self) -> LLMConfig:
        if self.llm_config is None:
            self.llm_config = LLMConfig.from_env()
        return self.llm_config

    def _read_pdf_pages(self, pdf_path: Path) -> list[dict[str, Any]]:
        reader = PdfReader(str(pdf_path))
        pages: list[dict[str, Any]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_whitespace(page.extract_text() or "")
            if text:
                pages.append({"page": page_number, "text": text})
        return pages

    def _chunk_pages(self, pages: list[dict[str, Any]], max_chunk_chars: int) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        current_pages: list[dict[str, Any]] = []
        current_chars = 0

        for page in pages:
            page_text = page["text"]
            if current_pages and current_chars + len(page_text) > max_chunk_chars:
                chunks.append(self._pages_to_chunk(current_pages))
                current_pages = []
                current_chars = 0
            current_pages.append(page)
            current_chars += len(page_text)

        if current_pages:
            chunks.append(self._pages_to_chunk(current_pages))
        return chunks

    def _pages_to_chunk(self, pages: list[dict[str, Any]]) -> TextChunk:
        start_page = pages[0]["page"]
        end_page = pages[-1]["page"]
        location = f"P{start_page}" if start_page == end_page else f"P{start_page}-P{end_page}"
        text = "\n\n".join(page["text"] for page in pages)
        return TextChunk(source_location=location, text=text)

    def _chunk_text(self, text: str, max_chunk_chars: int) -> list[TextChunk]:
        normalized = text.strip()
        if not normalized:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        if not paragraphs:
            paragraphs = [normalized]

        chunks: list[TextChunk] = []
        current_parts: list[str] = []
        current_chars = 0
        chunk_index = 1
        for paragraph in paragraphs:
            if current_parts and current_chars + len(paragraph) > max_chunk_chars:
                chunks.append(TextChunk(source_location=f"chunk-{chunk_index}", text="\n\n".join(current_parts)))
                current_parts = []
                current_chars = 0
                chunk_index += 1
            current_parts.append(paragraph)
            current_chars += len(paragraph)

        if current_parts:
            chunks.append(TextChunk(source_location=f"chunk-{chunk_index}", text="\n\n".join(current_parts)))
        return chunks

    def _empty_extraction(self) -> dict[str, Any]:
        return {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _label_communities(
        self,
        graph: Any,
        communities: dict[int, Iterable[str]],
    ) -> dict[int, str]:
        labels: dict[int, str] = {}
        for community_id, node_ids in communities.items():
            ranked = sorted(node_ids, key=lambda node_id: graph.degree(node_id), reverse=True)
            label = next(
                (
                    graph.nodes[node_id].get("label", node_id)
                    for node_id in ranked
                    if not str(graph.nodes[node_id].get("source_file", "")).endswith(".pdf")
                ),
                f"Community {community_id}",
            )
            labels[community_id] = label
        return labels

    def close(self) -> None:
        self._client = None
