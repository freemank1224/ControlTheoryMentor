"""Unit tests for Phase 2 dual-track tutor planning engine."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.node import NodeSummary
from app.schemas.tutor import (
    CourseType,
    TeachingPlan,
    TutorAnalyzeConcept,
    TutorAnalyzeResponse,
    TutorEvidencePassage,
    TutorMode,
    TutorSessionStartRequest,
)
from app.services.session_service import InMemorySessionStore, SessionService
from app.services.tutor_service import TutorService


def _build_analysis() -> TutorAnalyzeResponse:
    node = NodeSummary(
        graphId="graph-task-123",
        id="concept-pid",
        label="PID Controller",
        nodeType="concept",
        fileType="pdf",
        community=1,
        sourceFile="chapter-3.pdf",
        sourceLocation="p.12",
        properties={},
    )
    concept = TutorAnalyzeConcept(
        node=node,
        matchScore=0.95,
        summary="前置概念 1 个，公式 1 个，例题 1 个。",
        prerequisitesCount=1,
        relatedCount=2,
    )
    evidence = TutorEvidencePassage(
        chunkId="chunk-pid-1",
        conceptId="concept-pid",
        conceptLabel="PID Controller",
        sourceFile="chapter-3.pdf",
        sourceLocation="p.12",
        pageStart=12,
        pageEnd=12,
        excerpt="Integral action removes steady-state error.",
        score=0.98,
    )
    return TutorAnalyzeResponse(
        graphId="graph-task-123",
        question="How does PID reduce steady-state error?",
        summary="PID is the primary concept.",
        relevantConcepts=[concept],
        highlightedNodeIds=["concept-pid", "concept-feedback"],
        evidencePassages=[evidence],
        suggestedSession={"mode": "interactive"},
        metadata={},
    )


def _projection(plan: TeachingPlan) -> dict:
    return {
        "planFinalized": plan.planFinalized,
        "steps": [
            {
                "id": step.id,
                "type": step.type.value,
                "requiresResponse": step.requiresResponse,
                "modalityPrimary": step.modalityPlan.primary.value,
                "modalitySecondary": [item.value for item in step.modalityPlan.secondary],
                "responseMode": step.modalityPlan.responseMode.value,
                "checkpointKind": step.checkpointSpec.kind if step.checkpointSpec else None,
                "targetContentTypes": [
                    item.value for item in (step.content.contentRequest.targetContentTypes if step.content.contentRequest else [])
                ],
                "renderHint": step.content.contentRequest.renderHint.value if step.content.contentRequest else None,
            }
            for step in plan.steps
        ],
    }


def _build_service() -> TutorService:
    session_service = SessionService(InMemorySessionStore(data={}), backend_name="memory-test")
    return TutorService(node_service=object(), session_service=session_service)


def test_knowledge_builder_golden_snapshot_is_stable():
    service = _build_service()
    analysis = _build_analysis()

    plan = service._build_teaching_plan(
        question="How does PID reduce steady-state error?",
        mode=TutorMode.INTERACTIVE,
        analysis=analysis,
        context={"learning_level": "beginner"},
        course_type=CourseType.KNOWLEDGE_LEARNING,
        personalization={"pendingReviewConceptIds": ["concept-feedback"]},
    )

    assert _projection(plan) == {
        "planFinalized": True,
        "steps": [
            {
                "id": "step-1",
                "type": "intro",
                "requiresResponse": False,
                "modalityPrimary": "markdown",
                "modalitySecondary": ["mermaid"],
                "responseMode": "passive",
                "checkpointKind": None,
                "targetContentTypes": ["markdown", "mermaid"],
                "renderHint": "markdown",
            },
            {
                "id": "step-2",
                "type": "concept",
                "requiresResponse": True,
                "modalityPrimary": "markdown",
                "modalitySecondary": ["interactive"],
                "responseMode": "interactive",
                "checkpointKind": "concept_check",
                "targetContentTypes": ["markdown", "interactive"],
                "renderHint": "markdown",
            },
            {
                "id": "step-3",
                "type": "practice",
                "requiresResponse": True,
                "modalityPrimary": "markdown",
                "modalitySecondary": ["interactive"],
                "responseMode": "interactive",
                "checkpointKind": "transfer_check",
                "targetContentTypes": ["markdown", "interactive"],
                "renderHint": "markdown",
            },
            {
                "id": "step-4",
                "type": "summary",
                "requiresResponse": False,
                "modalityPrimary": "markdown",
                "modalitySecondary": [],
                "responseMode": "passive",
                "checkpointKind": None,
                "targetContentTypes": ["markdown"],
                "renderHint": "markdown",
            },
        ],
    }


def test_problem_builder_golden_snapshot_is_stable():
    service = _build_service()
    analysis = _build_analysis()

    plan = service._build_teaching_plan(
        question="Given G(s)=1/(s+1), calculate Kp.",
        mode=TutorMode.PROBLEM_SOLVING,
        analysis=analysis,
        context={"learning_level": "intermediate"},
        course_type=CourseType.PROBLEM_SOLVING,
        personalization={"pendingReviewConceptIds": ["concept-feedback"]},
    )

    assert _projection(plan) == {
        "planFinalized": True,
        "steps": [
            {
                "id": "step-1",
                "type": "intro",
                "requiresResponse": False,
                "modalityPrimary": "markdown",
                "modalitySecondary": ["latex"],
                "responseMode": "passive",
                "checkpointKind": None,
                "targetContentTypes": ["markdown", "latex"],
                "renderHint": "markdown",
            },
            {
                "id": "step-2",
                "type": "checkpoint",
                "requiresResponse": True,
                "modalityPrimary": "interactive",
                "modalitySecondary": ["markdown"],
                "responseMode": "interactive",
                "checkpointKind": "variable_constraint_check",
                "targetContentTypes": ["interactive", "markdown"],
                "renderHint": "interactive",
            },
            {
                "id": "step-3",
                "type": "practice",
                "requiresResponse": True,
                "modalityPrimary": "latex",
                "modalitySecondary": ["markdown", "interactive"],
                "responseMode": "interactive",
                "checkpointKind": "derivation_check",
                "targetContentTypes": ["latex", "markdown", "interactive"],
                "renderHint": "latex",
            },
            {
                "id": "step-4",
                "type": "summary",
                "requiresResponse": False,
                "modalityPrimary": "markdown",
                "modalitySecondary": [],
                "responseMode": "passive",
                "checkpointKind": None,
                "targetContentTypes": ["markdown"],
                "renderHint": "markdown",
            },
        ],
    }


def test_legacy_session_is_backfilled_for_course_type_and_plan_contract():
    session_service = SessionService(InMemorySessionStore(data={}), backend_name="memory-test")
    service = TutorService(node_service=object(), session_service=session_service)
    now = datetime.now(timezone.utc).isoformat()

    legacy_payload = {
        "id": "session-legacy",
        "question": "Explain PID controllers",
        "pdfId": "graph-task-123",
        "mode": "interactive",
        "context": {"learning_level": "beginner"},
        "analysis": {},
        "learningSnapshot": {},
        "topics": ["PID Controller"],
        "plan": {
            "summary": "legacy plan",
            "goals": ["legacy goal"],
            "steps": [
                {
                    "id": "step-1",
                    "type": "intro",
                    "title": "legacy intro",
                    "objective": "legacy objective",
                    "content": {"markdown": "legacy"},
                    "relatedTopics": ["concept-pid"],
                    "requiresResponse": False,
                },
                {
                    "id": "step-2",
                    "type": "concept",
                    "title": "legacy concept",
                    "objective": "legacy concept objective",
                    "content": {"markdown": "legacy concept"},
                    "relatedTopics": ["concept-pid"],
                    "requiresResponse": True,
                },
            ],
        },
        "messages": [],
        "currentStepIndex": -1,
        "status": "ready",
        "awaitingResponse": False,
        "createdAt": now,
        "updatedAt": now,
    }
    session_service.save_session(legacy_payload)

    response = service.get_session("session-legacy")

    assert response.metadata["finalCourseType"] in {"knowledge_learning", "problem_solving"}
    assert response.plan.planFinalized is True
    assert response.plan.steps[0].modalityPlan.primary.value == "markdown"
    assert response.plan.steps[1].checkpointSpec is not None
    assert response.plan.steps[1].checkpointSpec.kind == "legacy_checkpoint"

    persisted = session_service.get_session("session-legacy")
    assert persisted is not None
    assert persisted["courseType"] in {"knowledge_learning", "problem_solving"}
    assert persisted["plan"]["planFinalized"] is True
    assert "modalityPlan" in persisted["plan"]["steps"][0]


def test_insufficient_grounding_uses_alignment_check_plan():
    service = _build_service()
    analysis = TutorAnalyzeResponse(
        graphId="graph-task-123",
        question="这是什么",
        summary="",
        relevantConcepts=[],
        highlightedNodeIds=[],
        evidencePassages=[],
        suggestedSession={},
        metadata={},
    )

    plan = service._build_teaching_plan(
        question="这是什么",
        mode=TutorMode.INTERACTIVE,
        analysis=analysis,
        context={"learning_level": "beginner"},
        course_type=CourseType.KNOWLEDGE_LEARNING,
        personalization=None,
    )

    assert plan.summary.startswith("问题“这是什么”当前证据对齐不足")
    assert len(plan.steps) == 1
    assert plan.steps[0].title == "图谱与问题对齐检查"
    assert plan.steps[0].requiresResponse is False
    assert "暂不生成具体课程内容" in (plan.steps[0].content.markdown or "")


def test_start_session_blocks_mismatch_when_domain_strict_enabled():
    service = _build_service()

    service._safe_graph_domain_compatibility = lambda _graph_id: {
        "expectedDomain": "control_theory",
        "detectedDomain": "biology",
        "compatible": False,
        "reason": "domain_mismatch",
        "strict": True,
        "confidence": 0.9,
        "matchedKeywords": ["cell"],
        "signalCount": 4,
        "documentTitles": ["biology"],
        "introPreview": ["cell membrane"],
        "domainPromptSeed": "title=biology",
    }

    request = TutorSessionStartRequest(
        question="讲一下细胞膜",
        pdfId="graph-domain-mismatch",
        mode=TutorMode.INTERACTIVE,
        domainStrict=True,
    )

    response = service.start_session(request)

    assert response.plan.summary.startswith("图谱已加载，但领域与导师系统配置不一致")
    assert response.plan.steps[0].title == "图谱领域检查"
    assert response.metadata["domainStrict"] is True


def test_start_session_allows_mismatch_when_domain_strict_disabled():
    service = _build_service()

    service._safe_graph_domain_compatibility = lambda _graph_id: {
        "expectedDomain": "control_theory",
        "detectedDomain": "biology",
        "compatible": False,
        "reason": "domain_mismatch",
        "strict": False,
        "confidence": 0.9,
        "matchedKeywords": ["cell"],
        "signalCount": 4,
        "documentTitles": ["biology"],
        "introPreview": ["cell membrane"],
        "domainPromptSeed": "title=biology",
    }
    service.analyze_question = lambda _req: _build_analysis()
    service._build_teaching_plan = lambda *_args, **_kwargs: TeachingPlan(
        summary="non-strict plan",
        goals=["goal"],
        steps=[],
        planFinalized=True,
    )
    service._hydrate_plan_content_artifacts = lambda _plan: None

    request = TutorSessionStartRequest(
        question="讲一下细胞膜",
        pdfId="graph-domain-mismatch",
        mode=TutorMode.INTERACTIVE,
        domainStrict=False,
    )

    response = service.start_session(request)

    assert response.plan.summary == "non-strict plan"
    assert response.metadata["domainStrict"] is False
    assert response.metadata["graphDomainCompatibility"]["compatible"] is False
