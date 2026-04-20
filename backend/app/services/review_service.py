"""Content Review Agent — quality gate for generated content artifacts.

This service evaluates generated content against the knowledge graph and
original source material, scoring for factual accuracy and alignment.

Score ≥ 85/100  → "pass":   artifact is delivered as-is.
Score < 85/100  → "revise": artifact is flagged and may be regenerated with
                             the review feedback injected into the prompt.

Environment variables:
    CONTENT_REVIEW_ENABLED        Enable automatic review during generation (default "false").
    CONTENT_REVIEW_MAX_RETRIES    Max regeneration retries on a failing score  (default "1").
    CONTENT_REVIEW_PASS_THRESHOLD Pass threshold, integer 0-100               (default "85").
    CONTENT_REVIEW_LLM_TIMEOUT    LLM call timeout in seconds                 (default "30").
    CONTENT_REVIEW_LLM_MAX_TOKENS Max output tokens for the reviewer LLM      (default "600").
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from urllib.request import Request, urlopen

from app.schemas.content import ContentArtifact
from app.schemas.review import (
    ConflictItem,
    ConflictSeverity,
    ConsistencyItem,
    ContentReviewResult,
)
from app.schemas.tutor import TeachingContentRequest
from app.services.graph_service import GraphService, GraphNotFoundError, get_graph_service

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

PASS_THRESHOLD = int(os.getenv("CONTENT_REVIEW_PASS_THRESHOLD", "85"))


def review_enabled() -> bool:
    """Return True when automatic review is enabled via env var."""
    return os.getenv("CONTENT_REVIEW_ENABLED", "false").lower() in ("1", "true", "yes")


def max_retries() -> int:
    return max(0, int(os.getenv("CONTENT_REVIEW_MAX_RETRIES", "1")))


# ---------------------------------------------------------------------------
# Review service
# ---------------------------------------------------------------------------


class ContentReviewService:
    """Evaluate generated content artifacts against reference material."""

    def __init__(self, graph_service: GraphService | None = None) -> None:
        self.graph_service = graph_service or get_graph_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review_artifact(
        self,
        artifact: ContentArtifact,
        request: TeachingContentRequest,
    ) -> ContentReviewResult:
        """Review *artifact* using *request* for context and graph data as reference.

        The method attempts an LLM-based review first.  If the LLM is not
        configured or the call fails it falls back to a lightweight rule-based
        scoring heuristic so the pipeline never stalls.
        """
        graph_id = request.graphId or ""
        reference_nodes, reference_chunks = self._load_reference(graph_id, request)

        llm_result = self._llm_review(artifact, request, reference_nodes, reference_chunks)
        if llm_result is not None:
            return llm_result

        # LLM unavailable — use rule-based fallback
        return self._rule_based_review(artifact, request, graph_id)

    # ------------------------------------------------------------------
    # Reference loading
    # ------------------------------------------------------------------

    def _load_reference(
        self,
        graph_id: str,
        request: TeachingContentRequest,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (graph_node_summaries, source_text_chunks) for the given graph."""
        nodes: list[dict[str, Any]] = []
        chunks: list[str] = []

        if not graph_id:
            # Fall back to evidence excerpts already embedded in the request
            chunks = list(request.evidenceExcerpts or [])
            return nodes, chunks

        try:
            snapshot = self.graph_service.get_graph_snapshot(graph_id)
        except (GraphNotFoundError, Exception):
            chunks = list(request.evidenceExcerpts or [])
            return nodes, chunks

        for node in list(snapshot.nodes_by_id.values())[:40]:
            nodes.append({
                "id": node.get("id", ""),
                "label": node.get("label", ""),
                "properties": node.get("properties", {}),
            })

        if snapshot.source_chunks:
            for chunk in snapshot.source_chunks[:20]:
                text = chunk.get("text", "") or chunk.get("content", "") or str(chunk)
                if text:
                    chunks.append(text[:400])

        # Supplement with evidence excerpts from the request itself
        for exc in (request.evidenceExcerpts or []):
            if exc not in chunks:
                chunks.append(exc)

        return nodes, chunks

    # ------------------------------------------------------------------
    # LLM-based review
    # ------------------------------------------------------------------

    def _llm_review(
        self,
        artifact: ContentArtifact,
        request: TeachingContentRequest,
        reference_nodes: list[dict[str, Any]],
        reference_chunks: list[str],
    ) -> ContentReviewResult | None:
        """Call the LLM reviewer. Returns None when LLM is not available."""

        api_key = (
            os.getenv("CONTENT_LLM_API_KEY")
            or os.getenv("GRAPHIFY_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        model = (
            os.getenv("CONTENT_LLM_MODEL")
            or os.getenv("GRAPHIFY_LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
        )
        base_url = (
            os.getenv("CONTENT_LLM_BASE_URL")
            or os.getenv("GRAPHIFY_LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        timeout_s = float(os.getenv("CONTENT_REVIEW_LLM_TIMEOUT", "30"))
        max_tokens = int(os.getenv("CONTENT_REVIEW_LLM_MAX_TOKENS", "700"))

        if not api_key or not model:
            return None

        system_prompt = (
            "你是严格、专业的教学内容质量审核 Agent。"
            "你将收到一份生成的教学内容（多种模态）和相应的知识图谱节点及原文参考片段。"
            "请对照参考资料审核生成内容，执行以下任务：\n"
            "1. 找出生成内容中与参考资料冲突或矛盾的地方（factual conflicts）。\n"
            "2. 确认生成内容中与参考资料一致的核心要点（consistencies）。\n"
            "3. 综合评分 0-100，其中：\n"
            "   - 与参考资料无明显冲突且内容质量良好 → ≥85\n"
            "   - 存在 WARNING 级冲突或内容质量欠佳 → 70-84\n"
            "   - 存在 CRITICAL 级冲突（严重错误事实）→ <70\n"
            "4. 仅当 score ≥ 85 时 recommendation = 'pass'，否则 recommendation = 'revise'。\n"
            "5. 写出简短的 qualityNotes（如建议修改方向）。\n\n"
            "必须以如下 JSON 格式回复（不要输出任何其他内容）：\n"
            "{\n"
            '  "score": <0-100整数>,\n'
            '  "conflicts": [\n'
            '    {"field": "<模态>", "description": "<描述>", "reference": "<参考原文片段>", "severity": "critical|warning|note"}\n'
            '  ],\n'
            '  "consistencies": [\n'
            '    {"field": "<模态>", "description": "<描述>"}\n'
            '  ],\n'
            '  "qualityNotes": "<综合说明及修改建议>"\n'
            "}"
        )

        user_prompt = self._build_review_prompt(artifact, request, reference_nodes, reference_chunks)

        raw_text, call_meta = self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )

        if raw_text is None:
            return None

        parsed = self._parse_review_json(raw_text)
        if parsed is None:
            return None

        score = max(0, min(100, int(parsed.get("score", 75))))
        has_critical = any(
            c.get("severity") == "critical" for c in parsed.get("conflicts", [])
        )
        passed = score >= PASS_THRESHOLD and not has_critical

        conflicts = [
            ConflictItem(
                field=c.get("field", "markdown"),
                description=c.get("description", ""),
                reference=c.get("reference", ""),
                severity=ConflictSeverity(c.get("severity", "warning"))
                if c.get("severity") in ("critical", "warning", "note")
                else ConflictSeverity.WARNING,
            )
            for c in parsed.get("conflicts", [])
        ]
        consistencies = [
            ConsistencyItem(
                field=c.get("field", "markdown"),
                description=c.get("description", ""),
            )
            for c in parsed.get("consistencies", [])
        ]

        return ContentReviewResult(
            artifactId=artifact.id,
            graphId=request.graphId or "",
            score=score,
            passed=passed,
            recommendation="pass" if passed else "revise",
            conflicts=conflicts,
            consistencies=consistencies,
            qualityNotes=parsed.get("qualityNotes", ""),
            reviewedAt=datetime.now(timezone.utc).isoformat(),
            reviewMeta={
                "method": "llm",
                "model": model,
                "provider": "anthropic-compatible" if "/anthropic" in base_url.lower() else "openai-compatible",
                "callMeta": call_meta,
            },
        )

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------

    def _rule_based_review(
        self,
        artifact: ContentArtifact,
        request: TeachingContentRequest,
        graph_id: str,
    ) -> ContentReviewResult:
        """Lightweight heuristic review when LLM is unavailable."""

        score = 75  # conservative baseline

        content_source = artifact.metadata.get("contentSource", "template")
        llm_attempted = artifact.metadata.get("llmAttempted", False)
        is_grounded = bool(
            (request.primaryConceptId or request.conceptIds) and request.evidenceExcerpts
        )

        if content_source == "llm":
            score = 87 if is_grounded else 82
        elif content_source == "template":
            score = 78 if is_grounded else 72
        else:
            score = 75

        # Penalise if LLM attempted but fell back (suggests content may be lower quality)
        if llm_attempted and content_source == "template":
            score = max(score - 5, 60)

        consistencies: list[ConsistencyItem] = []
        if is_grounded:
            consistencies.append(
                ConsistencyItem(
                    field="markdown",
                    description="内容以图谱概念节点为基础生成，与参考资料领域一致",
                )
            )
        if artifact.latex:
            consistencies.append(
                ConsistencyItem(
                    field="latex",
                    description="包含领域相关公式占位",
                )
            )

        passed = score >= PASS_THRESHOLD
        notes = (
            "LLM 未配置，使用启发式评分。"
            if not llm_attempted
            else "LLM 调用失败，使用启发式评分。"
        )
        if not passed:
            notes += " 建议配置 CONTENT_LLM_* 环境变量以启用精确审核，或补充图谱证据摘录后重试。"

        return ContentReviewResult(
            artifactId=artifact.id,
            graphId=graph_id,
            score=score,
            passed=passed,
            recommendation="pass" if passed else "revise",
            conflicts=[],
            consistencies=consistencies,
            qualityNotes=notes,
            reviewedAt=datetime.now(timezone.utc).isoformat(),
            reviewMeta={"method": "rule_based", "contentSource": content_source},
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_review_prompt(
        artifact: ContentArtifact,
        request: TeachingContentRequest,
        reference_nodes: list[dict[str, Any]],
        reference_chunks: list[str],
    ) -> str:
        parts: list[str] = []

        parts.append("=== 生成内容 ===")
        parts.append(f"stepTitle: {request.stepTitle}")
        parts.append(f"objective: {request.objective}")
        parts.append(f"question: {request.question}")
        parts.append(f"learnerLevel: {request.learnerLevel}")
        parts.append(f"domain: {request.domainLabel or 'unknown'}")
        parts.append("")

        if artifact.markdown:
            parts.append("--- markdown ---")
            parts.append(artifact.markdown[:1200])
            parts.append("")

        if artifact.mermaid:
            parts.append("--- mermaid ---")
            parts.append(artifact.mermaid[:400])
            parts.append("")

        if artifact.latex:
            parts.append("--- latex ---")
            parts.append(artifact.latex[:300])
            parts.append("")

        if artifact.interactive:
            prompt_text = artifact.interactive.get("prompt", "")
            if prompt_text:
                parts.append("--- interactive prompt ---")
                parts.append(prompt_text[:300])
                parts.append("")

        parts.append("=== 参考资料 ===")

        if reference_nodes:
            parts.append("-- 知识图谱节点 --")
            for node in reference_nodes[:20]:
                label = node.get("label", node.get("id", ""))
                props = node.get("properties", {})
                desc = props.get("description", "") or props.get("definition", "") or ""
                if label:
                    line = f"• {label}"
                    if desc:
                        line += f": {str(desc)[:120]}"
                    parts.append(line)
            parts.append("")

        if reference_chunks:
            parts.append("-- 原文参考片段 --")
            for idx, chunk in enumerate(reference_chunks[:8], 1):
                parts.append(f"[{idx}] {chunk[:400]}")
                parts.append("")

        if not reference_nodes and not reference_chunks:
            parts.append("（未找到参考资料，请仅基于内容质量评分）")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # LLM call helper (same dual-protocol pattern as ContentService)
    # ------------------------------------------------------------------

    @staticmethod
    def _call_llm(
        *,
        system_prompt: str,
        user_prompt: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float,
        max_tokens: int,
    ) -> tuple[str | None, dict[str, Any]]:
        meta: dict[str, Any] = {"attempted": True, "error": None}
        try:
            if "/anthropic" in base_url.lower():
                url = f"{base_url}/v1/messages" if not base_url.endswith("/v1/messages") else base_url
                payload = {
                    "model": model,
                    "temperature": 0.1,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
                }
                req = Request(
                    url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "x-api-key": api_key,
                        "anthropic-version": os.getenv("GRAPHIFY_LLM_ANTHROPIC_VERSION", "2023-06-01"),
                        "content-type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(req, timeout=max(timeout_s, 5.0)) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = "\n".join(
                    b.get("text", "")
                    for b in data.get("content", [])
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
                return (text or None), meta

            url = f"{base_url}/chat/completions"
            payload = {
                "model": model,
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            req = Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                method="POST",
            )
            with urlopen(req, timeout=max(timeout_s, 5.0)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                meta["error"] = "no_choices"
                return None, meta
            text = (choices[0].get("message", {}).get("content", "") or "").strip()
            return (text or None), meta

        except Exception as exc:
            meta["error"] = f"{type(exc).__name__}:{exc}"[:220]
            return None, meta

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_review_json(raw: str) -> dict[str, Any] | None:
        """Extract and parse the JSON object from the LLM response."""
        # Strip markdown code fences if present
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # Find first { … } block
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_review_service: ContentReviewService | None = None


def get_review_service() -> ContentReviewService:
    """Return the shared ContentReviewService instance."""
    global _review_service
    if _review_service is None:
        _review_service = ContentReviewService(get_graph_service())
    return _review_service


def reset_review_service() -> None:
    """Reset the cached service instance (for tests)."""
    global _review_service
    _review_service = None
