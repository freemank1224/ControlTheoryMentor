"""Content generation service and persistence for P3 content artifacts."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid
from typing import Any, Callable, Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import close_redis_client, get_redis_client
from app.schemas.content import ContentArtifact, ContentArtifactStatus, ContentGenerationParams
from app.schemas.tutor import ContentArtifactType, ContentRequestResponseMode, CourseType, TeachingContentRequest

# Review service imported lazily to avoid a circular import; the TYPE_CHECKING
# guard keeps mypy happy without a hard dependency at module load time.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.review_service import ContentReviewService


class ContentStore(Protocol):
    """Storage contract for content artifacts and cache mappings."""

    def save(self, payload: dict[str, Any]) -> None:
        ...

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        ...

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        ...


def _clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


@dataclass
class InMemoryContentStore:
    """In-memory content storage for tests and fallback scenarios."""

    artifacts: dict[str, dict[str, Any]]
    cache_index: dict[str, str]

    def save(self, payload: dict[str, Any]) -> None:
        artifact_id = payload["id"]
        cache_key = payload["cacheKey"]
        self.artifacts[artifact_id] = _clone_payload(payload)
        self.cache_index[cache_key] = artifact_id

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        payload = self.artifacts.get(artifact_id)
        return _clone_payload(payload) if payload else None

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        artifact_id = self.cache_index.get(cache_key)
        if artifact_id is None:
            return None
        return self.get(artifact_id)


class RedisContentStore:
    """Redis-backed content storage with cache key lookups."""

    def __init__(
        self,
        client: Redis,
        artifact_prefix: str = "content:artifact",
        cache_prefix: str = "content:cache",
    ) -> None:
        self.client = client
        self.artifact_prefix = artifact_prefix
        self.cache_prefix = cache_prefix

    def save(self, payload: dict[str, Any]) -> None:
        artifact_id = payload["id"]
        cache_key = payload["cacheKey"]
        encoded = json.dumps(payload, ensure_ascii=False)
        pipe = self.client.pipeline()
        pipe.set(self._artifact_key(artifact_id), encoded)
        pipe.set(self._cache_key(cache_key), artifact_id)
        pipe.execute()

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        encoded = self.client.get(self._artifact_key(artifact_id))
        if not encoded:
            return None
        return json.loads(encoded)

    def get_by_cache_key(self, cache_key: str) -> dict[str, Any] | None:
        artifact_id = self.client.get(self._cache_key(cache_key))
        if not artifact_id:
            return None
        return self.get(artifact_id)

    def _artifact_key(self, artifact_id: str) -> str:
        return f"{self.artifact_prefix}:{artifact_id}"

    def _cache_key(self, cache_key: str) -> str:
        return f"{self.cache_prefix}:{cache_key}"


class ContentService:
    """Generate, cache, and retrieve content artifacts."""

    def __init__(
        self,
        store: ContentStore,
        backend_name: str,
        *,
        image_fetcher: Callable[[str, int], tuple[str, bytes]] | None = None,
        image_real_enabled: bool = True,
        review_service: "ContentReviewService | None" = None,
    ) -> None:
        self.store = store
        self.backend_name = backend_name
        self.image_fetcher = image_fetcher or self._fetch_real_image
        self.image_real_enabled = image_real_enabled
        # Optional review agent — injected at construction or via get_content_service().
        # Set to None to disable the review gate (useful in tests).
        self._review_service: "ContentReviewService | None" = review_service

    def generate_content(
        self,
        request: TeachingContentRequest,
        *,
        force_regenerate: bool = False,
        interactive_mode: str | None = None,
        generation_params: ContentGenerationParams | None = None,
    ) -> tuple[ContentArtifact, bool]:
        from app.services.review_service import review_enabled, max_retries

        params = generation_params or ContentGenerationParams()
        cache_key = self.build_cache_key(request, params)
        if not force_regenerate:
            cached = self.store.get_by_cache_key(cache_key)
            if cached is not None:
                return ContentArtifact.model_validate(cached), True

        artifact = self._build_artifact(
            request,
            cache_key=cache_key,
            interactive_mode=interactive_mode,
            generation_params=params,
        )

        # ── Content Review Gate ──────────────────────────────────────────────
        # When review is enabled and a review_service is wired in, evaluate the
        # artifact against the knowledge graph + source material.  If the score
        # falls below the pass threshold, regenerate up to max_retries times
        # with the review feedback injected into the LLM prompt.
        if review_enabled() and self._review_service is not None:
            review_result = self._review_service.review_artifact(artifact, request)
            _retries = 0
            _max = max_retries()
            while not review_result.passed and _retries < _max:
                _retries += 1
                feedback = self._format_review_feedback(review_result)
                artifact = self._build_artifact(
                    request,
                    cache_key=cache_key,
                    interactive_mode=interactive_mode,
                    generation_params=params,
                    review_feedback=feedback,
                )
                review_result = self._review_service.review_artifact(artifact, request)

            # Store review result inside the artifact metadata
            updated_meta = dict(artifact.metadata)
            updated_meta["review"] = review_result.model_dump(mode="json")
            artifact = artifact.model_copy(update={"metadata": updated_meta})
        # ── End Review Gate ─────────────────────────────────────────────────

        self.store.save(artifact.model_dump(mode="json"))
        return artifact, False

    @staticmethod
    def _format_review_feedback(review_result: Any) -> str:
        """Render reviewer findings as a concise feedback string for the LLM."""
        lines = ["以下是内容审核 Agent 的反馈，请在重新生成时针对性修正："]
        for conflict in (review_result.conflicts or []):
            severity = getattr(conflict, "severity", "warning")
            if hasattr(severity, "value"):
                severity = severity.value
            lines.append(f"- [{severity.upper()}] {conflict.description}（参考原文: {conflict.reference[:80]}）")
        if review_result.qualityNotes:
            lines.append(f"总体评估：{review_result.qualityNotes}")
        lines.append(f"当前得分：{review_result.score}/100，需达到 85 分以上方可通过。")
        return "\n".join(lines)

    def get_artifact(self, artifact_id: str) -> ContentArtifact | None:
        payload = self.store.get(artifact_id)
        if payload is None:
            return None
        return ContentArtifact.model_validate(payload)

    @staticmethod
    def build_cache_key(request: TeachingContentRequest, generation_params: ContentGenerationParams) -> str:
        payload = {
            "request": request.model_dump(mode="json"),
            "generationParams": generation_params.model_dump(mode="json"),
            "generatorVersion": os.getenv("CONTENT_GENERATOR_VERSION", "v2"),
        }
        fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_artifact(
        self,
        request: TeachingContentRequest,
        *,
        cache_key: str,
        interactive_mode: str | None,
        generation_params: ContentGenerationParams,
        review_feedback: str | None = None,
    ) -> ContentArtifact:
        now = datetime.now(timezone.utc).isoformat()
        artifact_id = f"content-{uuid.uuid4()}"
        requested_types = request.targetContentTypes or [ContentArtifactType.MARKDOWN]
        render_hint = request.renderHint

        markdown_meta: dict[str, Any] = {
            "source": "not_requested",
            "provider": None,
            "model": None,
            "llmAttempted": False,
            "llmFallbackReason": None,
        }
        markdown = None
        if ContentArtifactType.MARKDOWN in requested_types:
            markdown, markdown_meta = self._generate_markdown(request, generation_params, review_feedback=review_feedback)
        mermaid = self._generate_mermaid(request) if ContentArtifactType.MERMAID in requested_types else None
        latex = self._generate_latex(request) if ContentArtifactType.LATEX in requested_types else None
        image = None
        comic = None
        animation = None
        image_generation_meta: dict[str, Any] = {"requested": False}

        if ContentArtifactType.IMAGE in requested_types:
            image_generation_meta["requested"] = True
            image = self._generate_image_payload(request, generation_params)
            image_generation_meta["mode"] = image.get("source")
            if image.get("source") == "fallback":
                image_generation_meta["fallbackReason"] = image.get("fallbackReason")
                if markdown is None:
                    markdown, markdown_meta = self._generate_markdown(request, generation_params)
                if render_hint == ContentArtifactType.IMAGE:
                    render_hint = ContentArtifactType.MARKDOWN

        if ContentArtifactType.COMIC in requested_types:
            comic = self._generate_comic_payload(request, generation_params, image)

        if ContentArtifactType.ANIMATION in requested_types:
            animation = self._generate_animation_payload(request, generation_params)

        interactive = (
            self._generate_interactive_payload(request, interactive_mode, generation_params)
            if ContentArtifactType.INTERACTIVE in requested_types
            else None
        )

        return ContentArtifact(
            id=artifact_id,
            status=ContentArtifactStatus.READY,
            renderHint=render_hint,
            targetContentTypes=requested_types,
            markdown=markdown,
            mermaid=mermaid,
            latex=latex,
            image=image,
            comic=comic,
            animation=animation,
            interactive=interactive,
            source=request,
            cacheKey=cache_key,
            createdAt=now,
            updatedAt=now,
            metadata={
                "generator": "llm-v1" if markdown_meta.get("source") == "llm" else "template-v2",
                "contentSource": markdown_meta.get("source"),
                "provider": markdown_meta.get("provider"),
                "model": markdown_meta.get("model"),
                "llmAttempted": markdown_meta.get("llmAttempted"),
                "llmFallbackReason": markdown_meta.get("llmFallbackReason"),
                "responseMode": request.responseMode,
                "domainLabel": request.domainLabel,
                "domainConfidence": request.domainConfidence,
                "sourceDocumentTitles": request.sourceDocumentTitles,
                "sourceIntroPreview": request.sourceIntroPreview,
                "generationParams": generation_params.model_dump(mode="json"),
                "imageGeneration": image_generation_meta,
                "store": self.backend_name,
            },
        )

    def _generate_markdown(
        self,
        request: TeachingContentRequest,
        generation_params: ContentGenerationParams,
        *,
        review_feedback: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        # Always attempt LLM first; template is only used as a last resort when LLM
        # is not configured or the call fails.
        llm_text, llm_meta = self._generate_markdown_with_llm(request, generation_params, review_feedback=review_feedback)
        if llm_text:
            return llm_text, {
                "source": "llm",
                "provider": llm_meta.get("provider"),
                "model": llm_meta.get("model"),
                "llmAttempted": bool(llm_meta.get("attempted")),
                "llmFallbackReason": None,
            }

        # LLM not configured or failed — fall back to template.
        # If there truly is no grounding signal at all, use the insufficient-grounding message.
        _ = review_feedback  # Not used in template path; consumed only by LLM path.
        fallback_reason = llm_meta.get("error") or "llm_unavailable"
        if not self._is_request_grounded(request):
            return self._generate_insufficient_grounding_markdown(request), {
                "source": "template",
                "provider": "template",
                "model": os.getenv("CONTENT_GENERATOR_VERSION", "v2"),
                "llmAttempted": bool(llm_meta.get("attempted")),
                "llmFallbackReason": fallback_reason,
            }
        return self._generate_markdown_template(request, generation_params), {
            "source": "template",
            "provider": "template",
            "model": os.getenv("CONTENT_GENERATOR_VERSION", "v2"),
            "llmAttempted": bool(llm_meta.get("attempted")),
            "llmFallbackReason": fallback_reason,
        }

    @staticmethod
    def _generate_markdown_template(request: TeachingContentRequest, generation_params: ContentGenerationParams) -> str:
        lines = [
            f"## {request.stepTitle}",
            "",
            request.objective,
            "",
            f"- Session Mode: {request.sessionMode.value}",
            f"- Learner Level: {request.learnerLevel}",
            f"- Stage: {request.stage.value}",
            f"- Style: {generation_params.style}",
            f"- Detail: {generation_params.detail}",
            f"- Pace: {generation_params.pace}",
        ]
        if request.primaryConceptId:
            lines.append(f"- Primary Concept: {request.primaryConceptId}")
        if request.conceptIds:
            lines.append(f"- Related Concepts: {', '.join(request.conceptIds[:5])}")
        if request.evidencePassageIds:
            lines.append(f"- Evidence Anchors: {', '.join(request.evidencePassageIds[:3])}")
        if request.evidenceExcerpts:
            lines.append(f"- Evidence Excerpts: {len(request.evidenceExcerpts)}")
        if request.domainLabel:
            lines.append(f"- Detected Domain: {request.domainLabel}")
        if request.sourceDocumentTitles:
            lines.append(f"- Source Titles: {', '.join(request.sourceDocumentTitles[:2])}")

        lines.extend(
            [
                "",
                "### Learner Question",
                request.question,
            ]
        )

        if request.sourceIntroPreview:
            lines.extend(["", "### Source Intro Preview"])
            for snippet in request.sourceIntroPreview[:2]:
                lines.append(f"- {snippet}")

        if request.evidenceExcerpts:
            lines.extend(["", "### Grounding Evidence"])
            for excerpt in request.evidenceExcerpts[:3]:
                lines.append(f"- {excerpt}")

        if request.responseMode == ContentRequestResponseMode.INTERACTIVE:
            lines.extend(
                [
                    "",
                    "### Checkpoint",
                    "请先用 2-3 句话复述核心概念，再给出一个你会使用该概念的具体场景。",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _generate_insufficient_grounding_markdown(request: TeachingContentRequest) -> str:
        lines = [
            f"## {request.stepTitle}",
            "",
            "信息不足：当前问题未与图谱证据形成稳定对齐，系统暂停生成具体课程内容。",
            "",
            "### 建议操作",
            "- 确认当前会话使用的 graphId/pdfId 是否对应本次上传材料",
            "- 在问题中加入材料里的核心术语后重试",
            "- 若仍无法对齐，请重新上传或切换到正确图谱",
            "",
            "### Learner Question",
            request.question,
        ]
        return "\n".join(lines)

    @staticmethod
    def _is_request_grounded(request: TeachingContentRequest) -> bool:
        has_concept = bool(request.primaryConceptId or request.conceptIds)
        has_evidence = bool(request.evidenceExcerpts)
        return has_concept and has_evidence

    def _generate_markdown_with_llm(
        self,
        request: TeachingContentRequest,
        generation_params: ContentGenerationParams,
        *,
        review_feedback: str | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
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
        timeout_seconds = float(os.getenv("CONTENT_LLM_TIMEOUT_SECONDS", "45"))
        max_tokens = int(os.getenv("CONTENT_LLM_MAX_OUTPUT_TOKENS", "900"))
        provider = "anthropic-compatible" if "/anthropic" in base_url.lower() else "openai-compatible"

        meta: dict[str, Any] = {
            "attempted": bool(api_key and model),
            "provider": provider,
            "model": model,
            "error": None,
        }

        if not api_key or not model:
            meta["error"] = "missing_api_key_or_model"
            return None, meta

        domain_label = request.domainLabel or "general"
        domain_confidence = request.domainConfidence if request.domainConfidence is not None else 0.0
        source_titles = ", ".join(request.sourceDocumentTitles[:3]) if request.sourceDocumentTitles else "-"
        source_intro = " | ".join(request.sourceIntroPreview[:2]) if request.sourceIntroPreview else "-"
        domain_prompt_seed = request.domainPromptSeed or ""

        # Build a strong domain-anchored system prompt.
        # When domain_label is known (not "general"), explicitly constrain the LLM persona and
        # forbid drifting into unrelated domains (e.g., control theory when graph is biology).
        if domain_label and domain_label != "general":
            domain_anchor = (
                f"你是 {domain_label} 领域的图谱证据驱动教学内容生成器。"
                f"当前上传材料所属领域为 {domain_label}（置信度 {domain_confidence:.2f}）。"
            )
            if domain_prompt_seed:
                domain_anchor += f"领域特征信号：{domain_prompt_seed}。"
            domain_anchor += (
                f"所有生成内容必须以 {domain_label} 领域的术语和视角讲解，"
                "严禁引入与本次上传材料无关的其他领域知识。"
            )
        else:
            domain_anchor = (
                "你是图谱证据驱动的教学内容生成器，内容领域由上传材料决定。"
            )

        system_prompt = (
            f"{domain_anchor}"
            "输出高质量教学 Markdown。"
            "要求：优先基于用户问题、图谱概念节点和证据摘录生成内容；"
            "若无证据摘录，则基于概念节点和领域知识进行讲解，并在结尾简短注明'本节内容基于图谱节点生成，如需更精确讲解请补充原始文档'；"
            "禁止返回 JSON，禁止代码块包裹，直接输出 Markdown 正文。"
        )
        # ── Common context header ──
        _ctx = (
            f"stepTitle: {request.stepTitle}\n"
            f"objective: {request.objective}\n"
            f"question: {request.question}\n"
            f"sessionMode: {request.sessionMode.value}\n"
            f"learnerLevel: {request.learnerLevel}\n"
            f"primaryConceptId: {request.primaryConceptId or '-'}\n"
            f"conceptIds: {', '.join(request.conceptIds[:8]) if request.conceptIds else '-'}\n"
            f"evidenceExcerpts: {' | '.join(request.evidenceExcerpts[:4]) if request.evidenceExcerpts else '-'}\n"
            f"sourceTitles: {source_titles}\n"
            f"sourceIntroPreview: {source_intro}\n"
            f"style: {generation_params.style}, detail: {generation_params.detail}, pace: {generation_params.pace}\n"
        )

        _course = getattr(request.courseType, "value", None) if request.courseType else "knowledge_learning"
        _stage = request.stage.value if request.stage else "intro"

        # ── problem_solving track ──
        if _course == "problem_solving":
            if _stage == "intro":
                _instruction = (
                    "\n请以以下格式输出（直接输出 Markdown，禁止 JSON 和代码块）：\n\n"
                    "## 题目建模\n\n"
                    "### 问题解读\n（2 句话说明这是什么类型的问题、最终要求什么量）\n\n"
                    "### 已知量\n（以 Markdown 表格列出所有已知条件：| 符号 | 含义 | 单位/约束 |）\n\n"
                    "### 未知量 / 目标量\n（明确列出需要求解的量）\n\n"
                    "### 约束条件\n（逐条列出必须满足的约束与边界条件）\n\n"
                    "### 求解路径概述\n（用 3-4 个编号步骤说明总体解题路线，不展开细节）\n\n"
                    "篇幅 200-360 中文字。"
                )
            elif _stage == "checkpoint":
                _instruction = (
                    "\n请以以下格式输出（直接输出 Markdown，禁止 JSON 和代码块）：\n\n"
                    "## 变量与约束核查\n\n"
                    "### 变量清单\n（按 已知量 / 未知量 / 辅助量 分组列出，每个变量给出符号与含义）\n\n"
                    "### 关键公式盘点\n（列出后续推导将用到的核心公式，每个公式用 $...$ 包裹并注明适用条件）\n\n"
                    "### 容易遗漏的前提\n（列出 2-3 个求解此类题时易被忽略的前提或约束）\n\n"
                    "> **进入推导前的自检清单**：请确认已知量完整、单位统一、目标量明确。\n\n"
                    "篇幅 200-340 中文字。"
                )
            elif _stage == "practice":
                _instruction = (
                    "\n这是本次教学最核心的环节。请按以下格式输出完整的逐步推导过程（禁止 JSON 和代码块，直接输出 Markdown）：\n\n"
                    "## 分步推导\n\n"
                    "每个步骤必须包含：步骤名称、核心公式（$...$ 行内或 $$...$$ 块级）、"
                    "推导逻辑说明 1-2 句、具体操作展开。\n\n"
                    "模板：\n"
                    "### 第 N 步：[步骤名]\n"
                    "**核心公式**：$$...$$\n"
                    "**推导逻辑**：（从上一步到这一步的因果关系，1-2 句）\n"
                    "**操作**：（具体代入、变换、化简，每行一步）\n\n"
                    "（重复以上模板直至推导完成）\n\n"
                    "### 结果验证\n（如何验证推导结果的正确性，给出 1-2 个验证思路）\n\n"
                    "### 关键公式汇总\n（列出本题所有关键公式，每个一行，用 $...$ 包裹）\n\n"
                    "篇幅 320-600 中文字，步骤不得截断，公式必须完整写出。"
                )
            else:  # summary
                _instruction = (
                    "\n请以以下格式输出（直接输出 Markdown，禁止 JSON 和代码块）：\n\n"
                    "## 解题模板\n\n"
                    "### 解题框架（可复用步骤）\n（用编号列表抽象出本题通用解题步骤，至少 4 步）\n\n"
                    "### 关键公式速查\n（列出本题核心公式，每个附一句适用场景说明，用 $...$ 包裹）\n\n"
                    "### 易错点警告\n（列出 2-3 个本类型题最常见的错误及纠正方法）\n\n"
                    "### 迁移提示\n（说明此解题框架可扩展到哪些变式题或相关主题）\n\n"
                    "篇幅 200-360 中文字。"
                )
        else:  # knowledge_learning (default)
            if _stage == "intro":
                _instruction = (
                    "\n请以以下格式输出（直接输出 Markdown，禁止 JSON 和代码块）：\n\n"
                    "## 背景建立与学习目标\n\n"
                    "### 问题解读\n（2-3 句话说明这个问题属于什么领域、问的是什么、为什么重要）\n\n"
                    "### 本节核心概念\n（列出 3-5 个将要深入讲解的核心概念，格式：**概念名**：一句话说明它是什么）\n\n"
                    "### 学习路线图\n（简述本次学习的 4 个步骤，让用户了解接下来的学习历程）\n\n"
                    "篇幅 180-320 中文字。"
                )
            elif _stage == "concept":
                _instruction = (
                    "\n请对核心概念逐一进行深度讲解（2-4 个概念）。"
                    "每个概念必须包含以下全部要素（缺一不可）：\n\n"
                    "格式模板：\n"
                    "### 概念 N：[概念名]\n"
                    "**定义**：（精确的 1-2 句话定义，使用领域专业术语）\n"
                    "**公式**：（如有对应公式，用 $...$ 包裹写出；若无，写'本概念无对应公式'）\n"
                    "**直觉类比**：（1 句话，用日常场景或简单物理现象类比）\n"
                    "**结构说明**：（1-2 句话描述此概念的内部结构或工作流程，Mermaid 图将从旁补充可视化）\n"
                    "> **🤔 理解检查**：（提出一个只有真正理解才能回答的具体问题，要求分析或推断，不能是定义复述）\n\n"
                    "（所有概念讲完后无需总结段落，直接结束）\n\n"
                    "篇幅 300-520 中文字，每个概念篇幅均衡。"
                )
            elif _stage in ("practice", "checkpoint"):
                _instruction = (
                    "\n请设计一个具体的迁移应用场景，直接输出以下格式（Markdown，禁止 JSON）：\n\n"
                    "## 应用迁移\n\n"
                    "### 场景描述\n（给出一个具体的工程或现实情境，2-3 句话，场景必须真实可信）\n\n"
                    "### 应用任务\n（明确说明用户需要完成什么分析或判断，任务要和本节概念直接相关）\n\n"
                    "### 分析提示\n（给出 3-4 个分步分析提示，引导思考，但不直接给出答案）\n\n"
                    "### 参考思路\n（给出解题思路轮廓，包含关键公式或逻辑步骤，不给完整答案）\n\n"
                    "> **互动问题**：（提出一个需要用户具体操作或推理的 checkpoint 问题）\n\n"
                    "篇幅 220-400 中文字。"
                )
            else:  # summary
                _instruction = (
                    "\n请以以下格式输出（直接输出 Markdown，禁止 JSON 和代码块）：\n\n"
                    "## 本节核心收获\n\n"
                    "### 关键知识点总结\n（3-5 个要点，每个 1-2 句话，包含对应公式符号（用 $...$）或核心关系）\n\n"
                    "### 常见误区\n（列出 1-2 个该主题下学习者最常犯的认知错误，并给出正确理解）\n\n"
                    "### 下一步学习建议\n（给出 2-3 个具体的后续探索方向，引导持续学习）\n\n"
                    "篇幅 200-360 中文字。"
                )

        user_prompt = _ctx + _instruction
        # Inject review feedback so the LLM can address the reviewer's findings.
        if review_feedback:
            user_prompt += (
                "\n\n=== 内容审核反馈（请针对以下问题进行修正后重新生成）===\n"
                + review_feedback
                + "\n=== 请在以上要求的格式下重新生成改进后的内容 ==="
            )

        try:
            if "/anthropic" in base_url.lower():
                messages_url = f"{base_url}/v1/messages" if not base_url.endswith("/v1/messages") else base_url
                payload = {
                    "model": model,
                    "temperature": 0.4,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
                }
                request_obj = Request(
                    messages_url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "x-api-key": api_key,
                        "anthropic-version": os.getenv("GRAPHIFY_LLM_ANTHROPIC_VERSION", "2023-06-01"),
                        "content-type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(request_obj, timeout=max(timeout_seconds, 5.0)) as response:
                    data = json.loads(response.read().decode("utf-8"))
                blocks = data.get("content", [])
                text = "\n".join(
                    block.get("text", "")
                    for block in blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                ).strip()
                if text:
                    return text, meta
                meta["error"] = "empty_response"
                return None, meta

            completions_url = f"{base_url}/chat/completions"
            payload = {
                "model": model,
                "temperature": 0.4,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            request_obj = Request(
                completions_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                method="POST",
            )
            with urlopen(request_obj, timeout=max(timeout_seconds, 5.0)) as response:
                data = json.loads(response.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                meta["error"] = "no_choices"
                return None, meta
            content = choices[0].get("message", {}).get("content", "")
            text = content.strip() if isinstance(content, str) else ""
            if text:
                return text, meta
            meta["error"] = "empty_response"
            return None, meta
        except Exception as exc:
            raw_error = f"{type(exc).__name__}:{exc}"
            meta["error"] = raw_error[:220]
            return None, meta

    @staticmethod
    def _sanitize_mermaid_label(label: str) -> str:
        return label.replace('"', "'").replace("[", "(").replace("]", ")")[:48]

    def _generate_mermaid(self, request: TeachingContentRequest) -> str:
        concepts = request.highlightedNodeIds or request.conceptIds or ([request.primaryConceptId] if request.primaryConceptId else [])
        lines = [
            "graph TD",
            f"  Q[\"{self._sanitize_mermaid_label(request.question)}\"] --> S[\"{self._sanitize_mermaid_label(request.stepTitle)}\"]",
        ]
        for index, concept in enumerate(concepts[:5], start=1):
            lines.append(f"  S --> C{index}[\"{self._sanitize_mermaid_label(concept)}\"]")
        if request.responseMode == ContentRequestResponseMode.INTERACTIVE:
            lines.append("  S --> R[\"Learner Response\"]")
        return "\n".join(lines)

    @staticmethod
    def _generate_latex(request: TeachingContentRequest) -> str:
        """Generate a domain-appropriate standalone LaTeX formula for the current step."""
        _course = getattr(request.courseType, "value", None) if request.courseType else "knowledge_learning"
        question_lower = request.question.lower()
        domain = (request.domainLabel or "").lower()
        concepts = " ".join(request.conceptIds[:5]).lower() if request.conceptIds else ""

        # Control / PID domain
        if any(kw in question_lower or kw in concepts for kw in ("pid", "积分", "微分", "controller", "控制器")):
            return r"u(t)=K_p e(t)+K_i\int_{0}^{t}e(\tau)\,d\tau+K_d\frac{de(t)}{dt}"
        if any(kw in question_lower for kw in ("传递函数", "transfer function", "laplace", "拉普拉斯")):
            return r"G(s)=\frac{Y(s)}{U(s)}=\frac{b_m s^m+\cdots+b_0}{a_n s^n+\cdots+a_0}"
        if any(kw in question_lower for kw in ("bode", "频率响应", "frequency response", "幅值", "相位")):
            return r"|G(j\omega)|_{\mathrm{dB}}=20\log_{10}|G(j\omega)|,\quad \angle G(j\omega)=\arg G(j\omega)"
        if any(kw in question_lower for kw in ("状态空间", "state space", "state-space")):
            return r"\dot{\mathbf{x}}=A\mathbf{x}+B\mathbf{u},\quad \mathbf{y}=C\mathbf{x}+D\mathbf{u}"
        if any(kw in question_lower for kw in ("稳定", "stability", "lyapunov", "routh", "nyquist")):
            return r"\mathrm{Re}(\lambda_i(A))<0 \iff \text{系统渐近稳定}"
        if any(kw in question_lower for kw in ("阶跃响应", "step response", "超调", "overshoot", "settling")):
            return r"M_p=e^{-\pi\zeta/\sqrt{1-\zeta^2}}\times 100\%,\quad t_s\approx\frac{4}{\zeta\omega_n}"
        # Physical / mechanical
        if any(kw in domain for kw in ("物理", "physics", "力学", "mechanics", "动力学")):
            return r"m\ddot{x}+c\dot{x}+kx=F(t)"
        # Electrical
        if any(kw in domain for kw in ("电路", "circuit", "电子", "electronics")):
            return r"V=IR,\quad P=\frac{V^2}{R}=I^2 R"
        # Problem-solving generic: use a cleaner placeholder than y=f(x)
        if _course == "problem_solving":
            primary = request.primaryConceptId or "x"
            return rf"f({primary})=\text{{目标量}}"
        return r"y = f(x)"

    @staticmethod
    def _generate_interactive_payload(
        request: TeachingContentRequest,
        interactive_mode: str | None,
        generation_params: ContentGenerationParams,
    ) -> dict[str, Any]:
        _course = getattr(request.courseType, "value", None) if request.courseType else "knowledge_learning"
        _stage = request.stage.value if request.stage else "intro"
        mode = interactive_mode or "guided"

        if _course == "problem_solving":
            if _stage == "checkpoint":
                prompt = (
                    f"请列出：① 已知量（至少 2 个，写出符号与含义）② 未知量/目标量 ③ 关键约束条件（至少 1 个）。"
                    f"主题：{request.stepTitle}"
                )
                expected = "structured-list"
                mode = "variable_inventory"
            elif _stage == "practice":
                prompt = (
                    f"请写出第一步的核心公式，并说明从题目条件到这一步的推导逻辑（1-2 句话）。"
                    f"主题：{request.stepTitle}"
                )
                expected = "formula-and-reasoning"
                mode = "derivation_step"
            else:
                prompt = f"根据 {request.stepTitle} 的解题模板，你会如何处理一道相似的变式题？请描述你的解题思路。"
                expected = "short-text"
                mode = "template_transfer"
        else:  # knowledge_learning
            if _stage == "concept":
                concept = request.primaryConceptId or request.stepTitle
                prompt = (
                    f"请用自己的话解释：{concept} 在本次问题中扮演什么角色？"
                    f"并给出一个你认为最能体现其核心作用的应用场景（1-2 句话）。"
                )
                expected = "short-text"
                mode = "concept_check"
            elif _stage in ("practice", "checkpoint"):
                prompt = (
                    f"根据上面的场景描述，请完成以下任务：{request.stepTitle}。"
                    f"写出你的分析思路（重点是思路，不需要完整答案）。"
                )
                expected = "analytical-response"
                mode = "transfer_apply"
            else:
                prompt = f"学完本节后，请用一句话总结 {request.stepTitle} 的核心要点。"
                expected = "short-text"
                mode = "reflection"

        return {
            "mode": mode,
            "status": "ready",
            "prompt": prompt,
            "expectedResponse": expected,
            "params": generation_params.model_dump(mode="json"),
        }

    def _generate_image_payload(
        self,
        request: TeachingContentRequest,
        generation_params: ContentGenerationParams,
    ) -> dict[str, Any]:
        prompt = generation_params.imagePrompt or self._build_image_prompt(request, generation_params)
        timeout_ms = generation_params.imageTimeoutMs

        if not self.image_real_enabled:
            return self._fallback_image_payload(prompt, "image_provider_disabled")

        try:
            mime_type, image_bytes = self.image_fetcher(prompt, timeout_ms)
            data_url = self._to_data_url(mime_type, image_bytes)
            return {
                "source": "real",
                "status": "ready",
                "mimeType": mime_type,
                "dataUrl": data_url,
                "alt": f"{request.stepTitle} image",
                "prompt": prompt,
            }
        except TimeoutError:
            return self._fallback_image_payload(prompt, "image_generation_timeout")
        except Exception as exc:
            return self._fallback_image_payload(prompt, f"image_generation_failed:{type(exc).__name__}")

    @staticmethod
    def _build_image_prompt(request: TeachingContentRequest, generation_params: ContentGenerationParams) -> str:
        return (
            f"{request.stepTitle}. {request.objective}. "
            f"style={generation_params.style}; detail={generation_params.detail}; pace={generation_params.pace}; "
            f"concept={request.primaryConceptId or 'topic'}"
        )

    @staticmethod
    def _to_data_url(mime_type: str, payload: bytes) -> str:
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _fallback_image_payload(prompt: str, reason: str) -> dict[str, Any]:
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='720' height='405'>"
            "<rect width='100%' height='100%' fill='#e8eef5'/>"
            "<rect x='24' y='24' width='672' height='357' fill='#ffffff' stroke='#9fb2c7' stroke-width='2'/>"
            "<text x='40' y='72' font-size='28' fill='#274c77'>Image fallback</text>"
            f"<text x='40' y='118' font-size='16' fill='#335c81'>{reason}</text>"
            f"<text x='40' y='160' font-size='14' fill='#4b6f8f'>{prompt[:110]}</text>"
            "</svg>"
        )
        data_url = "data:image/svg+xml;utf8," + quote(svg)
        return {
            "source": "fallback",
            "status": "fallback",
            "mimeType": "image/svg+xml",
            "dataUrl": data_url,
            "alt": "Image fallback",
            "prompt": prompt,
            "fallbackReason": reason,
        }

    @staticmethod
    def _generate_comic_payload(
        request: TeachingContentRequest,
        generation_params: ContentGenerationParams,
        image_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "status": "ready",
            "source": "placeholder",
            "style": generation_params.style,
            "panels": [
                {
                    "id": "panel-1",
                    "caption": f"问题设定: {request.question}",
                    "visual": image_payload.get("dataUrl") if image_payload else None,
                },
                {
                    "id": "panel-2",
                    "caption": f"核心目标: {request.objective}",
                    "visual": None,
                },
            ],
        }

    @staticmethod
    def _generate_animation_payload(
        request: TeachingContentRequest,
        generation_params: ContentGenerationParams,
    ) -> dict[str, Any]:
        return {
            "status": "placeholder",
            "source": "placeholder",
            "format": "timeline-v1",
            "pace": generation_params.pace,
            "keyframes": [
                {"t": 0, "label": "setup", "text": request.stepTitle},
                {"t": 1, "label": "focus", "text": request.objective},
                {"t": 2, "label": "prompt", "text": request.question},
            ],
        }

    @staticmethod
    def _fetch_real_image(prompt: str, timeout_ms: int) -> tuple[str, bytes]:
        timeout_seconds = max(timeout_ms / 1000.0, 0.2)
        encoded_prompt = quote(prompt, safe="")
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=432&nologo=true"
        request = Request(url, headers={"User-Agent": "ControlTheoryMentor/1.0"}, method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "image/jpeg")
        except URLError as exc:
            reason = str(getattr(exc, "reason", exc)).lower()
            if "timed out" in reason:
                raise TimeoutError("image generation timed out") from exc
            raise

        if not payload:
            raise RuntimeError("empty image payload")
        mime_type = content_type.split(";")[0].strip() or "image/jpeg"
        if not mime_type.startswith("image/"):
            raise RuntimeError("unexpected image mime type")
        return mime_type, payload


class FailoverContentService(ContentService):
    """Content service that falls back to memory when Redis is unavailable."""

    def __init__(
        self,
        primary_store: ContentStore,
        fallback_store: InMemoryContentStore,
        healthcheck: Callable[[], None],
        primary_backend_name: str = "redis",
        fallback_backend_name: str = "memory-fallback",
        review_service: "ContentReviewService | None" = None,
    ) -> None:
        super().__init__(
            store=primary_store,
            backend_name=primary_backend_name,
            review_service=review_service,
        )
        self.primary_store = primary_store
        self.fallback_store = fallback_store
        self.healthcheck = healthcheck
        self.primary_backend_name = primary_backend_name
        self.fallback_backend_name = fallback_backend_name

    def generate_content(
        self,
        request: TeachingContentRequest,
        *,
        force_regenerate: bool = False,
        interactive_mode: str | None = None,
        generation_params: ContentGenerationParams | None = None,
    ) -> tuple[ContentArtifact, bool]:
        return self._run_with_failover(
            lambda: ContentService.generate_content(
                self,
                request,
                force_regenerate=force_regenerate,
                interactive_mode=interactive_mode,
                generation_params=generation_params,
            )
        )

    def get_artifact(self, artifact_id: str) -> ContentArtifact | None:
        return self._run_with_failover(lambda: ContentService.get_artifact(self, artifact_id))

    def _run_with_failover(self, action: Callable[[], Any]) -> Any:
        if self.backend_name == self.fallback_backend_name and not self._try_restore_primary():
            return action()

        try:
            return action()
        except RedisError:
            self._set_fallback()
            return action()

    def _try_restore_primary(self) -> bool:
        try:
            self.healthcheck()
        except RedisError:
            self._set_fallback()
            return False
        self._set_primary()
        return True

    def _set_primary(self) -> None:
        self.store = self.primary_store
        self.backend_name = self.primary_backend_name

    def _set_fallback(self) -> None:
        self.store = self.fallback_store
        self.backend_name = self.fallback_backend_name


_content_service: ContentService | None = None
_fallback_store = InMemoryContentStore(artifacts={}, cache_index={})


def get_content_service() -> ContentService:
    """Return the default content service with Redis-first failover behavior."""

    global _content_service
    if _content_service is not None:
        return _content_service

    client = get_redis_client()

    # Wire the review service when CONTENT_REVIEW_ENABLED is set.
    _review_svc = None
    if os.getenv("CONTENT_REVIEW_ENABLED", "false").lower() in ("1", "true", "yes"):
        from app.services.review_service import get_review_service
        _review_svc = get_review_service()

    service = FailoverContentService(
        primary_store=RedisContentStore(client),
        fallback_store=_fallback_store,
        healthcheck=client.ping,
        review_service=_review_svc,
    )
    try:
        client.ping()
        _content_service = service
    except RedisError:
        service._set_fallback()
        _content_service = service
    return _content_service


def reset_content_service() -> None:
    """Reset cached content service and fallback storage."""

    global _content_service
    _content_service = None
    _fallback_store.artifacts.clear()
    _fallback_store.cache_index.clear()
    close_redis_client()
