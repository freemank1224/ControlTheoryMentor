"""Tutor orchestration service for analyze, planning, and session state transitions."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Any

from fastapi import HTTPException

from app.schemas.learning import LearningEventType, LearningProgress, LearningTrackRequest
from app.services.content_service import ContentService, get_content_service
from app.schemas.tutor import (
    ContentArtifactType,
    ContentRequestResponseMode,
    MessageType,
    TeachingPlan,
    TeachingContentRequest,
    TeachingStep,
    TeachingStepType,
    TutorAnalyzeConcept,
    TutorAnalyzeRequest,
    TutorAnalyzeResponse,
    TutorEvidencePassage,
    TutorMessage,
    TutorMode,
    TutorSessionJumpRequest,
    TutorSessionListItem,
    TutorSessionRespondRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionStatus,
    TutorSessionsResponse,
)
from app.services.learning_service import LearningService, get_learning_service
from app.services.node_service import NodeService, get_node_service
from app.services.session_service import SessionService, get_session_service

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "does",
    "for",
    "from",
    "how",
    "into",
    "that",
    "the",
    "this",
    "what",
    "with",
    "would",
}


class TutorService:
    """Graph-grounded tutor orchestration and session persistence."""

    def __init__(
        self,
        node_service: NodeService | None = None,
        session_service: SessionService | None = None,
        content_service: ContentService | None = None,
        learning_service: LearningService | None = None,
    ) -> None:
        self.node_service = node_service or get_node_service()
        self.session_service = session_service or get_session_service()
        self.content_service = content_service or get_content_service()
        self.learning_service = learning_service or get_learning_service()

    def analyze_question(self, request: TutorAnalyzeRequest) -> TutorAnalyzeResponse:
        learner_id = self._resolve_learner_id(request.learnerId, request.context)
        learning_progress = self._safe_get_learning_progress(learner_id, request.pdfId)
        search = self.node_service.semantic_search(request.pdfId, request.question, limit=request.limit)
        concepts: list[TutorAnalyzeConcept] = []
        evidence_passages: list[TutorEvidencePassage] = []
        highlighted_node_ids: list[str] = []

        for item in search["items"]:
            context = self.node_service.get_concept_context(request.pdfId, item["id"])
            concepts.append(
                TutorAnalyzeConcept(
                    node=item,
                    matchScore=float(item.get("score") or 0.0),
                    summary=self._build_concept_summary(context),
                    prerequisitesCount=len(context["prerequisites"]),
                    relatedCount=len(context["relatedNodes"]),
                )
            )
            highlighted_node_ids.append(item["id"])
            evidence_passages.extend(self._rank_passages(request.question, item["label"], item["id"], context["passages"]))

        evidence_passages.sort(key=lambda passage: passage.score, reverse=True)
        evidence_passages = evidence_passages[: request.limit]
        primary_concept = concepts[0].node.id if concepts else None
        summary = self._build_analysis_summary(request.question, concepts, evidence_passages, learning_progress)

        suggested_session = {
            "mode": request.mode,
            "primaryConceptId": primary_concept,
            "sessionStore": self.session_service.backend_name,
        }
        personalization = self._build_personalization_snapshot(learning_progress)
        if personalization:
            suggested_session["personalization"] = personalization

        return TutorAnalyzeResponse(
            graphId=request.pdfId,
            question=request.question,
            summary=summary,
            relevantConcepts=concepts,
            highlightedNodeIds=highlighted_node_ids,
            evidencePassages=evidence_passages,
            suggestedSession=suggested_session,
        )

    def start_session(self, request: TutorSessionStartRequest) -> TutorSessionResponse:
        learner_id = self._resolve_learner_id(request.learnerId, request.context)
        learning_progress = self._safe_get_learning_progress(learner_id, request.pdfId)
        personalization = self._build_personalization_snapshot(learning_progress)
        analysis = self.analyze_question(
            TutorAnalyzeRequest(
                question=request.question,
                pdfId=request.pdfId,
                learnerId=learner_id,
                mode=request.mode,
                context=request.context,
                limit=3,
            )
        )
        session_id = f"session-{uuid.uuid4()}"
        now = self._utc_now_iso()
        plan = self._build_teaching_plan(
            request.question,
            request.mode,
            analysis,
            request.context or {},
            personalization=personalization,
        )
        self._hydrate_plan_content_artifacts(plan)

        session = {
            "id": session_id,
            "question": request.question,
            "pdfId": request.pdfId,
            "learnerId": learner_id,
            "mode": request.mode.value,
            "context": request.context or {},
            "analysis": analysis.model_dump(mode="json"),
            "learningSnapshot": personalization,
            "topics": [concept.node.label for concept in analysis.relevantConcepts],
            "plan": plan.model_dump(mode="json"),
            "messages": [
                TutorMessage(
                    role=MessageType.SYSTEM,
                    content=f"Tutor session started for question: {request.question}",
                    metadata={
                        "event": "session_started",
                        "pdfId": request.pdfId,
                        "topics": [concept.node.id for concept in analysis.relevantConcepts],
                        "learnerId": learner_id,
                    },
                ).model_dump(mode="json")
            ],
            "currentStepIndex": -1,
            "status": TutorSessionStatus.READY.value,
            "awaitingResponse": False,
            "createdAt": now,
            "updatedAt": now,
        }
        self.session_service.save_session(session)
        self._track_learning_event(
            session,
            event_type=LearningEventType.SESSION_STARTED,
            metadata={"mode": request.mode.value},
        )
        return self._build_session_response(session)

    def get_session(self, session_id: str) -> TutorSessionResponse:
        session = self._require_session(session_id)
        return self._build_session_response(session)

    def list_sessions(self, limit: int = 50) -> TutorSessionsResponse:
        sessions = self.session_service.list_sessions(limit=limit)
        items: list[TutorSessionListItem] = []
        for session in sessions:
            plan = TeachingPlan.model_validate(session["plan"])
            current_index = int(session.get("currentStepIndex", -1))
            current_title = None
            if 0 <= current_index < len(plan.steps):
                current_title = plan.steps[current_index].title
            items.append(
                TutorSessionListItem(
                    sessionId=session["id"],
                    question=session["question"],
                    pdfId=session["pdfId"],
                    mode=session["mode"],
                    status=session["status"],
                    currentStepIndex=current_index,
                    currentStepTitle=current_title,
                    topics=session.get("topics", []),
                    updatedAt=session.get("updatedAt", ""),
                )
            )
        return TutorSessionsResponse(items=items, total=len(items), metadata={"store": self.session_service.backend_name})

    def advance_session(self, session_id: str) -> TutorSessionResponse:
        session = self._require_session(session_id)
        plan = TeachingPlan.model_validate(session["plan"])
        status = TutorSessionStatus(session["status"])
        current_index = int(session["currentStepIndex"])

        if status == TutorSessionStatus.COMPLETED:
            return self._build_session_response(session, feedback="This session is already complete.")
        if session["awaitingResponse"]:
            raise HTTPException(status_code=409, detail="Current step requires a learner response before advancing.")

        if 0 <= current_index < len(plan.steps):
            self._track_learning_event(
                session,
                event_type=LearningEventType.STEP_COMPLETED,
                step=plan.steps[current_index],
                completed_step=True,
                metadata={"event": "step_completed"},
            )

        next_index = current_index + 1
        if next_index >= len(plan.steps):
            session["status"] = TutorSessionStatus.COMPLETED.value
            session["currentStepIndex"] = len(plan.steps)
            completion_message = self._build_completion_message(session)
            self._append_message(session, MessageType.ASSISTANT, completion_message, {"event": "session_completed"})
            self._track_learning_event(
                session,
                event_type=LearningEventType.SESSION_COMPLETED,
                metadata={"event": "session_completed", "totalSteps": len(plan.steps)},
            )
            self._touch_session(session)
            self.session_service.save_session(session)
            return self._build_session_response(session, feedback=completion_message)

        self._activate_step(session, plan.steps[next_index], next_index, event="step_started")
        session["plan"] = plan.model_dump(mode="json")
        self.session_service.save_session(session)
        return self._build_session_response(session)

    def respond_to_session(self, session_id: str, request: TutorSessionRespondRequest) -> TutorSessionResponse:
        session = self._require_session(session_id)
        plan = TeachingPlan.model_validate(session["plan"])
        current_index = int(session["currentStepIndex"])
        if current_index < 0 or current_index >= len(plan.steps):
            raise HTTPException(status_code=409, detail="No active teaching step to respond to.")
        if not session["awaitingResponse"]:
            raise HTTPException(status_code=409, detail="Current step does not require a learner response.")

        step = plan.steps[current_index]
        self._append_message(
            session,
            MessageType.USER,
            request.response,
            {"event": "step_response", "stepId": step.id, **request.metadata},
        )
        feedback = self._generate_step_feedback(step, request.response, session)
        self._append_message(session, MessageType.ASSISTANT, feedback, {"event": "step_feedback", "stepId": step.id})
        self._track_learning_event(
            session,
            event_type=LearningEventType.STEP_RESPONSE,
            step=step,
            confidence=self._coerce_confidence(request.metadata.get("confidence")),
            metadata={"event": "step_response", "responseLength": len(request.response.strip())},
        )
        session["awaitingResponse"] = False
        session["status"] = TutorSessionStatus.READY.value
        self._touch_session(session)
        self.session_service.save_session(session)
        return self._build_session_response(session, feedback=feedback)

    def back_session(self, session_id: str) -> TutorSessionResponse:
        session = self._require_session(session_id)
        plan = TeachingPlan.model_validate(session["plan"])
        current_index = int(session["currentStepIndex"])
        if current_index <= 0:
            session["currentStepIndex"] = -1
            session["awaitingResponse"] = False
            session["status"] = TutorSessionStatus.READY.value
            self._touch_session(session)
            self.session_service.save_session(session)
            return self._build_session_response(session, feedback="Moved back to the session overview.")

        previous_index = current_index - 1
        self._activate_step(session, plan.steps[previous_index], previous_index, event="step_revisited")
        session["plan"] = plan.model_dump(mode="json")
        self.session_service.save_session(session)
        return self._build_session_response(session, feedback="Moved back to the previous step.")

    def jump_session(self, session_id: str, request: TutorSessionJumpRequest) -> TutorSessionResponse:
        session = self._require_session(session_id)
        plan = TeachingPlan.model_validate(session["plan"])
        target_index = self._resolve_jump_target(plan, request)
        self._activate_step(session, plan.steps[target_index], target_index, event="step_jumped")
        session["plan"] = plan.model_dump(mode="json")
        self.session_service.save_session(session)
        return self._build_session_response(session, feedback=f"Jumped to {plan.steps[target_index].title}.")

    def _resolve_jump_target(self, plan: TeachingPlan, request: TutorSessionJumpRequest) -> int:
        if request.stepIndex is not None:
            if request.stepIndex < 0 or request.stepIndex >= len(plan.steps):
                raise HTTPException(status_code=400, detail="stepIndex is out of range.")
            return request.stepIndex
        if request.stepId is not None:
            for index, step in enumerate(plan.steps):
                if step.id == request.stepId:
                    return index
            raise HTTPException(status_code=404, detail="stepId not found in the session plan.")
        raise HTTPException(status_code=400, detail="Either stepIndex or stepId is required.")

    def _activate_step(self, session: dict[str, Any], step: TeachingStep, index: int, *, event: str) -> None:
        self._ensure_step_content_artifact(step)
        session["currentStepIndex"] = index
        session["awaitingResponse"] = step.requiresResponse
        session["status"] = (
            TutorSessionStatus.AWAITING_RESPONSE.value if step.requiresResponse else TutorSessionStatus.IN_PROGRESS.value
        )
        self._append_message(
            session,
            MessageType.ASSISTANT,
            self._render_step_message(step, session),
            {"event": event, "stepId": step.id, "stepType": step.type.value},
        )
        self._track_learning_event(
            session,
            event_type=LearningEventType.STEP_STARTED,
            step=step,
            metadata={"event": event, "stepType": step.type.value},
        )
        self._touch_session(session)

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Tutor session not found")
        return session

    def _build_session_response(self, session: dict[str, Any], feedback: str | None = None) -> TutorSessionResponse:
        plan = TeachingPlan.model_validate(session["plan"])
        current_step_index = int(session.get("currentStepIndex", -1))
        current_step = plan.steps[current_step_index] if 0 <= current_step_index < len(plan.steps) else None
        messages = [TutorMessage.model_validate(message) for message in session.get("messages", [])]
        return TutorSessionResponse(
            sessionId=session["id"],
            plan=plan,
            currentStep=current_step,
            currentStepIndex=current_step_index,
            status=TutorSessionStatus(session["status"]),
            messages=messages,
            canAdvance=session["status"] != TutorSessionStatus.COMPLETED.value and not session["awaitingResponse"],
            needsUserResponse=bool(session["awaitingResponse"]),
            feedback=feedback,
            metadata={
                "pdfId": session["pdfId"],
                "question": session["question"],
                "learnerId": session.get("learnerId"),
                "mode": session["mode"],
                "topics": session.get("topics", []),
                "totalSteps": len(plan.steps),
                "createdAt": session.get("createdAt"),
                "updatedAt": session.get("updatedAt"),
                "store": self.session_service.backend_name,
                "analysis": session.get("analysis"),
                "learningSnapshot": session.get("learningSnapshot", {}),
            },
        )

    def _build_teaching_plan(
        self,
        question: str,
        mode: TutorMode,
        analysis: TutorAnalyzeResponse,
        context: dict[str, Any],
        *,
        personalization: dict[str, Any] | None = None,
    ) -> TeachingPlan:
        primary_label = analysis.relevantConcepts[0].node.label if analysis.relevantConcepts else "control theory"
        learner_level = str(context.get("learning_level", "intermediate"))
        evidence = [passage.model_dump(mode="json") for passage in analysis.evidencePassages[:2]]
        highlights = analysis.highlightedNodeIds[:4]
        weak_concepts = list(personalization.get("pendingReviewConceptIds", []) if personalization else [])
        weak_focus = weak_concepts[0] if weak_concepts else None

        steps = [
            TeachingStep(
                id="step-1",
                type=TeachingStepType.INTRO,
                title=f"建立问题背景: {primary_label}",
                objective="明确问题、目标概念和教材证据来源。",
                content={
                    "markdown": f"我们先围绕“{question}”确认主概念 {primary_label}，并结合教材原文片段建立讲解边界。",
                    "graphHighlights": highlights,
                    "evidencePassages": evidence,
                    "contentRequest": self._build_content_request(
                        TeachingStepType.INTRO,
                        analysis,
                        learner_level,
                        question=question,
                        mode=mode,
                        step_id="step-1",
                        step_title=f"建立问题背景: {primary_label}",
                        objective="明确问题、目标概念和教材证据来源。",
                        requires_response=False,
                    ),
                },
                relatedTopics=[concept.node.id for concept in analysis.relevantConcepts],
                requiresResponse=False,
            ),
            TeachingStep(
                id="step-2",
                type=TeachingStepType.CONCEPT,
                title=f"拆解核心概念: {primary_label}",
                objective="将概念拆成更适合理解检查的子点。",
                content={
                    "markdown": f"现在拆解 {primary_label} 的核心作用、前置知识和常见误区，并用原文证据支撑关键说法。",
                    "guidingQuestion": f"请你用自己的话解释 {primary_label} 在控制系统中的作用。",
                    "graphHighlights": highlights,
                    "evidencePassages": evidence,
                    "contentRequest": self._build_content_request(
                        TeachingStepType.CONCEPT,
                        analysis,
                        learner_level,
                        question=question,
                        mode=mode,
                        step_id="step-2",
                        step_title=f"拆解核心概念: {primary_label}",
                        objective="将概念拆成更适合理解检查的子点。",
                        requires_response=True,
                    ),
                },
                relatedTopics=[concept.node.id for concept in analysis.relevantConcepts],
                requiresResponse=True,
            ),
            TeachingStep(
                id="step-3",
                type=TeachingStepType.PRACTICE if mode != TutorMode.QUIZ else TeachingStepType.CHECKPOINT,
                title="理解检查与迁移",
                objective="把概念迁移到更具体的问题场景。",
                content={
                    "markdown": self._build_practice_markdown(mode, primary_label, weak_concepts),
                    "prompt": self._build_practice_prompt(mode, primary_label, weak_concepts),
                    "graphHighlights": highlights,
                    "evidencePassages": [passage.model_dump(mode="json") for passage in analysis.evidencePassages[1:3]],
                    "contentRequest": self._build_content_request(
                        TeachingStepType.PRACTICE if mode != TutorMode.QUIZ else TeachingStepType.CHECKPOINT,
                        analysis,
                        learner_level,
                        question=question,
                        mode=mode,
                        step_id="step-3",
                        step_title="理解检查与迁移",
                        objective="把概念迁移到更具体的问题场景。",
                        requires_response=True,
                    ),
                },
                relatedTopics=[concept.node.id for concept in analysis.relevantConcepts],
                requiresResponse=True,
            ),
            TeachingStep(
                id="step-4",
                type=TeachingStepType.SUMMARY,
                title="总结与下一步",
                objective="收束本轮学习，并给出下一步建议。",
                content={
                    "markdown": "最后把本轮核心结论收束成可复述的要点，并明确下一步应继续追踪的图谱节点。",
                    "nextActions": [
                        f"回看与 {primary_label} 直接相关的图谱节点",
                        f"补练概念 {weak_focus}" if weak_focus else "补练当前掌握最弱的一个概念节点",
                        "基于教材原文重新复述关键定义",
                        "继续追问一个前置概念或例题节点",
                    ],
                    "graphHighlights": highlights,
                    "evidencePassages": evidence,
                    "contentRequest": self._build_content_request(
                        TeachingStepType.SUMMARY,
                        analysis,
                        learner_level,
                        question=question,
                        mode=mode,
                        step_id="step-4",
                        step_title="总结与下一步",
                        objective="收束本轮学习，并给出下一步建议。",
                        requires_response=False,
                    ),
                },
                relatedTopics=[concept.node.id for concept in analysis.relevantConcepts],
                requiresResponse=False,
            ),
        ]
        return TeachingPlan(
            summary=f"围绕“{question}”的图谱 + 原文证据四步教学计划。",
            goals=[
                f"识别 {primary_label} 的核心作用",
                "能够引用教材证据复述关键概念",
                "把概念迁移到具体控制场景中使用",
                f"优先补强薄弱概念：{weak_focus}" if weak_focus else "记录并回顾当前未稳固概念",
            ],
            steps=steps,
        )

    def _build_content_request(
        self,
        stage: TeachingStepType,
        analysis: TutorAnalyzeResponse,
        learner_level: str,
        *,
        question: str,
        mode: TutorMode,
        step_id: str,
        step_title: str,
        objective: str,
        requires_response: bool,
    ) -> TeachingContentRequest:
        return TeachingContentRequest(
            stage=stage,
            stepId=step_id,
            stepTitle=step_title,
            objective=objective,
            question=question,
            graphId=analysis.graphId,
            sessionMode=mode,
            learnerLevel=learner_level,
            responseMode=(
                ContentRequestResponseMode.INTERACTIVE
                if requires_response
                else ContentRequestResponseMode.PASSIVE
            ),
            primaryConceptId=analysis.relevantConcepts[0].node.id if analysis.relevantConcepts else None,
            conceptIds=[concept.node.id for concept in analysis.relevantConcepts],
            highlightedNodeIds=analysis.highlightedNodeIds,
            evidencePassageIds=[passage.chunkId for passage in analysis.evidencePassages[:3]],
            targetContentTypes=[ContentArtifactType.MARKDOWN],
            renderHint=ContentArtifactType.MARKDOWN,
        )

    def _rank_passages(
        self,
        question: str,
        concept_label: str,
        concept_id: str,
        passages: list[dict[str, Any]],
    ) -> list[TutorEvidencePassage]:
        query_tokens = self._tokenize(question)
        concept_tokens = self._tokenize(concept_label)
        ranked: list[TutorEvidencePassage] = []
        for passage in passages:
            sentences = self._split_sentences(passage.get("text") or "")
            if not sentences:
                continue
            best_sentence = max(sentences, key=lambda candidate: self._sentence_score(candidate, query_tokens, concept_tokens))
            score = self._sentence_score(best_sentence, query_tokens, concept_tokens)
            ranked.append(
                TutorEvidencePassage(
                    chunkId=passage["chunkId"],
                    conceptId=concept_id,
                    conceptLabel=concept_label,
                    sourceFile=passage["sourceFile"],
                    sourceLocation=passage.get("sourceLocation"),
                    pageStart=passage.get("pageStart"),
                    pageEnd=passage.get("pageEnd"),
                    excerpt=best_sentence,
                    score=round(score, 4),
                )
            )
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def _build_concept_summary(self, context: dict[str, Any]) -> str:
        prerequisites = len(context.get("prerequisites", []))
        formulas = len(context.get("formulas", []))
        examples = len(context.get("examples", []))
        return f"前置概念 {prerequisites} 个，公式 {formulas} 个，例题 {examples} 个。"

    def _build_analysis_summary(
        self,
        question: str,
        concepts: list[TutorAnalyzeConcept],
        evidence_passages: list[TutorEvidencePassage],
        learning_progress: LearningProgress | None = None,
    ) -> str:
        if not concepts:
            return f"未在图谱中稳定匹配到与“{question}”直接对应的概念，建议先降级到全文搜索或人工指定章节。"
        primary = concepts[0].node.label
        summary = (
            f"问题“{question}”当前最相关的主概念是 {primary}，并已抽取 {len(evidence_passages)} 条优先原文证据供 tutor 编排使用。"
        )
        if learning_progress is None:
            return summary
        pending_count = len(learning_progress.pendingReviewConceptIds)
        mastered_count = len(learning_progress.masteredConceptIds)
        return (
            f"{summary} 当前学习状态显示已掌握 {mastered_count} 个概念，"
            f"待复习 {pending_count} 个概念，将用于后续个性化编排。"
        )

    def _render_step_message(self, step: TeachingStep, session: dict[str, Any]) -> str:
        question = session["question"]
        base = f"[{step.title}] {step.content.markdown or ''}"
        if step.requiresResponse:
            prompt = step.content.guidingQuestion or step.content.prompt
            return f"{base}\n\n请基于你的问题“{question}”回答：{prompt}"
        return base

    def _generate_step_feedback(self, step: TeachingStep, response: str, session: dict[str, Any]) -> str:
        concise = response.strip()
        word_count = len([part for part in concise.replace("\n", " ").split(" ") if part])
        topics = session.get("topics", [])
        primary_topic = topics[0] if topics else "the topic"
        if word_count < 6:
            return f"你的回答方向是对的，但还比较简略。建议再补一句：{primary_topic} 影响了系统的哪个行为，以及为什么。"
        return f"你的回答已经覆盖了 {step.title} 的关键点。下一步可以继续检查你是否能把 {primary_topic} 放进更具体的系统场景里使用。"

    def _build_completion_message(self, session: dict[str, Any]) -> str:
        topics = session.get("topics", [])
        primary_topic = topics[0] if topics else "control theory"
        return f"本轮关于 {primary_topic} 的教学会话已经完成。你现在可以回到知识图谱继续追踪相关节点，或者围绕同一主题发起下一轮更深入的问题。"

    def _append_message(self, session: dict[str, Any], role: MessageType, content: str, metadata: dict[str, Any]) -> None:
        session.setdefault("messages", []).append(
            TutorMessage(role=role, content=content, metadata=metadata).model_dump(mode="json")
        )

    def _hydrate_plan_content_artifacts(self, plan: TeachingPlan) -> None:
        for step in plan.steps:
            self._ensure_step_content_artifact(step)

    def _ensure_step_content_artifact(self, step: TeachingStep) -> None:
        if step.content.contentArtifactId:
            return
        if step.content.contentRequest is None:
            return
        try:
            artifact, _ = self.content_service.generate_content(step.content.contentRequest)
            step.content.contentArtifactId = artifact.id
            step.content.contentArtifactStatus = artifact.status.value
            step.content.contentArtifactUpdatedAt = artifact.updatedAt
        except Exception:
            step.content.contentArtifactStatus = "failed"

    def _touch_session(self, session: dict[str, Any]) -> None:
        session["updatedAt"] = self._utc_now_iso()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]
        return sentences or ([text.strip()] if text.strip() else [])

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9_+-]+", text.lower())
            if len(token) >= 3 and token not in STOPWORDS
        }

    def _sentence_score(self, sentence: str, query_tokens: set[str], concept_tokens: set[str]) -> float:
        tokens = self._tokenize(sentence)
        if not tokens:
            return 0.0
        query_overlap = len(tokens & query_tokens) / max(len(query_tokens), 1)
        concept_overlap = len(tokens & concept_tokens) / max(len(concept_tokens), 1)
        return 0.85 * query_overlap + 0.15 * concept_overlap

    @staticmethod
    def _build_practice_markdown(mode: TutorMode, primary_topic: str, weak_concepts: list[str] | None = None) -> str:
        focus_hint = f" 当前建议优先补练概念：{weak_concepts[0]}。" if weak_concepts else ""
        if mode == TutorMode.QUIZ:
            return f"进入快速检查：判断你是否已经能区分 {primary_topic} 的功能、限制和适用场景。{focus_hint}"
        if mode == TutorMode.PROBLEM_SOLVING:
            return f"把 {primary_topic} 放入一个具体求解场景，说明你会先抓哪些变量与约束。{focus_hint}"
        return f"把 {primary_topic} 应用到一个更具体的系统或情境中，看看理解是否能迁移。{focus_hint}"

    @staticmethod
    def _build_practice_prompt(mode: TutorMode, primary_topic: str, weak_concepts: list[str] | None = None) -> str:
        focus_hint = f" 并优先提到 {weak_concepts[0]}。" if weak_concepts else ""
        if mode == TutorMode.QUIZ:
            return f"给出一个简短判断：什么时候 {primary_topic} 会失效或不再适用？{focus_hint}"
        if mode == TutorMode.PROBLEM_SOLVING:
            return f"如果你要基于 {primary_topic} 解题，请先列出最关键的两个已知量和一个目标量。{focus_hint}"
        return f"请举一个你会用到 {primary_topic} 的实际或教材场景，并说明原因。{focus_hint}"

    @staticmethod
    def _resolve_learner_id(explicit_learner_id: str | None, context: dict[str, Any] | None) -> str | None:
        if explicit_learner_id:
            return explicit_learner_id
        if not context:
            return None
        for key in ("learnerId", "learner_id", "userId", "user_id"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _safe_get_learning_progress(self, learner_id: str | None, graph_id: str) -> LearningProgress | None:
        if not learner_id:
            return None
        try:
            return self.learning_service.get_progress(learner_id, graph_id)
        except Exception:
            return None

    @staticmethod
    def _build_personalization_snapshot(progress: LearningProgress | None) -> dict[str, Any]:
        if progress is None:
            return {}
        return {
            "masteredConceptIds": progress.masteredConceptIds,
            "pendingReviewConceptIds": progress.pendingReviewConceptIds,
            "averageFeedbackRating": progress.averageFeedbackRating,
            "eventCount": progress.eventCount,
        }

    @staticmethod
    def _coerce_confidence(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            numeric = float(value)
            return max(0.0, min(1.0, numeric))
        if isinstance(value, str):
            aliases = {
                "low": 0.25,
                "medium": 0.5,
                "high": 0.85,
            }
            candidate = aliases.get(value.strip().lower())
            if candidate is not None:
                return candidate
            try:
                numeric = float(value)
            except ValueError:
                return None
            return max(0.0, min(1.0, numeric))
        return None

    def _track_learning_event(
        self,
        session: dict[str, Any],
        *,
        event_type: LearningEventType,
        step: TeachingStep | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        completed_step: bool = False,
    ) -> None:
        learner_id = session.get("learnerId")
        if not learner_id:
            return

        concept_id = step.relatedTopics[0] if step and step.relatedTopics else None
        step_id = step.id if step else session.get("currentStepId")
        try:
            self.learning_service.track_event(
                LearningTrackRequest(
                    learnerId=learner_id,
                    graphId=session["pdfId"],
                    sessionId=session["id"],
                    stepId=step_id,
                    conceptId=concept_id,
                    eventType=event_type,
                    confidence=confidence,
                    completedStep=completed_step,
                    metadata=metadata or {},
                )
            )
        except Exception:
            return


def get_tutor_service() -> TutorService:
    """FastAPI dependency for the tutor orchestration service."""
    return TutorService()