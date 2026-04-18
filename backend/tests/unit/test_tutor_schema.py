"""
Unit tests for Tutor schema
"""
import pytest
from pydantic import ValidationError
from app.schemas.tutor import (
    ContentArtifactType,
    ContentRequestResponseMode,
    TeachingPlan,
    TeachingContentRequest,
    TeachingStep,
    TeachingStepContent,
    TeachingStepType,
    TutorMessage,
    TutorAnalyzeConcept,
    TutorAnalyzeRequest,
    TutorAnalyzeResponse,
    TutorEvidencePassage,
    TutorRequest,
    TutorResponse,
    TutorSessionJumpRequest,
    TutorSessionListItem,
    TutorSessionRespondRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionStatus,
    TutorSessionsResponse,
    MessageType,
    TutorMode
)
from app.schemas.node import NodeSummary


class TestTutorMessage:
    """Test TutorMessage schema"""

    def test_tutor_message_success(self):
        """Test successful tutor message creation"""
        message = TutorMessage(
            role="user",
            content="Explain PID controllers"
        )
        assert message.role == "user"
        assert message.content == "Explain PID controllers"
        assert message.metadata == {}

    def test_tutor_message_with_metadata(self):
        """Test tutor message with metadata"""
        message = TutorMessage(
            role="assistant",
            content="PID controllers have three components...",
            metadata={"confidence": 0.9, "sources": ["textbook"]}
        )
        assert message.metadata["confidence"] == 0.9
        assert message.metadata["sources"] == ["textbook"]

    def test_tutor_message_invalid_role(self):
        """Test tutor message with invalid role"""
        with pytest.raises(ValidationError):
            TutorMessage(
                role="invalid_role",
                content="Test message"
            )


class TestTutorRequest:
    """Test TutorRequest schema"""

    def test_tutor_request_success(self):
        """Test successful tutor request"""
        request = TutorRequest(
            message="Explain transfer functions",
            mode="interactive"
        )
        assert request.message == "Explain transfer functions"
        assert request.mode == TutorMode.INTERACTIVE
        assert request.context is None

    def test_tutor_request_with_context(self):
        """Test tutor request with context"""
        request = TutorRequest(
            message="What is feedback?",
            mode="interactive",
            context={
                "current_topic": "control systems",
                "learning_level": "beginner"
            }
        )
        assert request.context["current_topic"] == "control systems"
        assert request.context["learning_level"] == "beginner"

    def test_tutor_request_missing_message(self):
        """Test tutor request without message"""
        with pytest.raises(ValidationError):
            TutorRequest(mode="interactive")

    def test_tutor_request_invalid_mode(self):
        """Test tutor request with invalid mode"""
        with pytest.raises(ValidationError):
            TutorRequest(
                message="Test",
                mode="invalid_mode"
            )


class TestTutorResponse:
    """Test TutorResponse schema"""

    def test_tutor_response_success(self):
        """Test successful tutor response"""
        response = TutorResponse(
            message="PID controllers are used to control systems...",
            conversation_id="conv-123",
            metadata={
                "confidence": 0.95,
                "topics_covered": ["PID", "control systems"]
            }
        )
        assert response.message == "PID controllers are used to control systems..."
        assert response.conversation_id == "conv-123"
        assert response.metadata["confidence"] == 0.95

    def test_tutor_response_with_suggestions(self):
        """Test tutor response with suggestions"""
        response = TutorResponse(
            message="Let me explain that...",
            conversation_id="conv-123",
            suggestions=[
                "Tell me more about proportional control",
                "How do I tune a PID controller?"
            ]
        )
        assert len(response.suggestions) == 2
        assert "How do I tune a PID controller?" in response.suggestions

    def test_tutor_response_empty_message(self):
        """Test tutor response with empty message"""
        with pytest.raises(ValidationError):
            TutorResponse(
                message="",
                conversation_id="conv-123"
            )


class TestTutorSessionSchemas:
    """Test step-by-step tutor session schemas"""

    def test_tutor_session_start_request_success(self):
        """Start request should accept question and PDF identifier"""
        request = TutorSessionStartRequest(
            question="Explain PID controllers",
            pdfId="graph-task-123",
            mode="interactive"
        )

        assert request.question == "Explain PID controllers"
        assert request.pdfId == "graph-task-123"
        assert request.mode == TutorMode.INTERACTIVE

    def test_tutor_session_respond_request_requires_response(self):
        """Respond request should reject empty responses"""
        with pytest.raises(ValidationError):
            TutorSessionRespondRequest(response="")

    def test_tutor_session_response_success(self):
        """Session response should serialize plan and step state"""
        step = TeachingStep(
            id="step-1",
            type=TeachingStepType.INTRO,
            title="建立问题背景",
            objective="明确学习目标",
            content={
                "markdown": "先建立背景",
                "contentRequest": {
                    "stage": "intro",
                    "stepId": "step-1",
                    "stepTitle": "建立问题背景",
                    "objective": "明确学习目标",
                    "question": "Explain PID controllers",
                    "graphId": "graph-task-123",
                    "sessionMode": "interactive",
                    "learnerLevel": "beginner",
                    "responseMode": "passive",
                    "primaryConceptId": "concept-pid",
                    "conceptIds": ["concept-pid"],
                    "highlightedNodeIds": ["concept-pid"],
                    "evidencePassageIds": ["chunk-pid-1"],
                    "targetContentTypes": ["markdown"],
                    "renderHint": "markdown",
                },
            }
        )
        plan = TeachingPlan(
            summary="四步教学计划",
            goals=["理解概念"],
            steps=[step]
        )

        response = TutorSessionResponse(
            sessionId="session-123",
            plan=plan,
            currentStep=step,
            currentStepIndex=0,
            status=TutorSessionStatus.IN_PROGRESS,
            messages=[],
            canAdvance=True,
            needsUserResponse=False,
            metadata={"pdfId": "graph-task-123"}
        )

        assert response.sessionId == "session-123"
        assert response.currentStep.id == "step-1"
        assert response.status == TutorSessionStatus.IN_PROGRESS
        assert response.metadata["pdfId"] == "graph-task-123"
        assert response.currentStep.content.contentRequest.stepId == "step-1"
        assert response.currentStep.content.contentRequest.responseMode == ContentRequestResponseMode.PASSIVE


class TestTutorAnalyzeSchemas:
    """Test graph-grounded tutor analyze schemas."""

    def test_tutor_analyze_request_defaults(self):
        request = TutorAnalyzeRequest(
            question="How does PID reduce steady-state error?",
            pdfId="graph-task-123",
        )

        assert request.mode == TutorMode.INTERACTIVE
        assert request.limit == 3
        assert request.context is None

    def test_tutor_evidence_passage_requires_excerpt(self):
        with pytest.raises(ValidationError):
            TutorEvidencePassage(
                chunkId="chunk-1",
                conceptId="concept-pid",
                conceptLabel="PID Controller",
                sourceFile="chapter-3.pdf",
                excerpt="",
                score=0.9,
            )

    def test_tutor_analyze_response_serializes_concepts_and_evidence(self):
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

        response = TutorAnalyzeResponse(
            graphId="graph-task-123",
            question="How does PID reduce steady-state error?",
            summary="PID is the primary concept.",
            relevantConcepts=[concept],
            highlightedNodeIds=["concept-pid"],
            evidencePassages=[evidence],
            suggestedSession={"mode": "interactive"},
        )

        assert response.relevantConcepts[0].node.id == "concept-pid"
        assert response.evidencePassages[0].pageStart == 12
        assert response.highlightedNodeIds == ["concept-pid"]


class TestTeachingContentSchemas:
    """Test stable content request contract handed to P3."""

    def test_teaching_content_request_serializes_stable_contract(self):
        request = TeachingContentRequest(
            stage=TeachingStepType.PRACTICE,
            stepId="step-3",
            stepTitle="理解检查与迁移",
            objective="把概念迁移到更具体的问题场景。",
            question="How does PID reduce steady-state error?",
            graphId="graph-task-123",
            sessionMode=TutorMode.QUIZ,
            learnerLevel="intermediate",
            responseMode=ContentRequestResponseMode.INTERACTIVE,
            primaryConceptId="concept-pid",
            conceptIds=["concept-pid", "concept-feedback"],
            highlightedNodeIds=["concept-pid"],
            evidencePassageIds=["chunk-pid-1", "chunk-feedback-1"],
            targetContentTypes=[ContentArtifactType.MARKDOWN, ContentArtifactType.INTERACTIVE],
            renderHint=ContentArtifactType.MARKDOWN,
        )

        assert request.stage == TeachingStepType.PRACTICE
        assert request.sessionMode == TutorMode.QUIZ
        assert request.responseMode == ContentRequestResponseMode.INTERACTIVE
        assert request.targetContentTypes == [ContentArtifactType.MARKDOWN, ContentArtifactType.INTERACTIVE]

    def test_teaching_step_content_accepts_evidence_and_contract(self):
        content = TeachingStepContent(
            markdown="先建立背景",
            graphHighlights=["concept-pid"],
            contentArtifactId="content-123",
            contentArtifactStatus="ready",
            contentArtifactUpdatedAt="2026-04-18T00:00:00Z",
            evidencePassages=[
                {
                    "chunkId": "chunk-pid-1",
                    "conceptId": "concept-pid",
                    "conceptLabel": "PID Controller",
                    "sourceFile": "chapter-3.pdf",
                    "excerpt": "Integral action removes steady-state error.",
                    "score": 0.98,
                }
            ],
            contentRequest={
                "stage": "intro",
                "stepId": "step-1",
                "stepTitle": "建立问题背景",
                "objective": "明确学习目标",
                "question": "Explain PID controllers",
                "graphId": "graph-task-123",
                "sessionMode": "interactive",
                "learnerLevel": "beginner",
                "responseMode": "passive",
                "primaryConceptId": "concept-pid",
                "conceptIds": ["concept-pid"],
                "highlightedNodeIds": ["concept-pid"],
                "evidencePassageIds": ["chunk-pid-1"],
                "targetContentTypes": ["markdown"],
                "renderHint": "markdown",
            },
        )

        assert content.evidencePassages[0].chunkId == "chunk-pid-1"
        assert content.contentRequest.graphId == "graph-task-123"
        assert content.contentArtifactId == "content-123"


class TestTutorSessionListingSchemas:
    """Test tutor session jump and listing schemas."""

    def test_tutor_session_jump_request_accepts_step_index(self):
        request = TutorSessionJumpRequest(stepIndex=2)
        assert request.stepIndex == 2
        assert request.stepId is None

    def test_tutor_session_list_response_defaults(self):
        item = TutorSessionListItem(
            sessionId="session-123",
            question="Explain PID controllers",
            pdfId="graph-task-123",
            mode="interactive",
            status="ready",
            updatedAt="2026-04-18T00:00:00Z",
        )
        response = TutorSessionsResponse(items=[item], total=1, metadata={"store": "memory-test"})

        assert response.total == 1
        assert response.items[0].currentStepIndex == -1
        assert response.metadata["store"] == "memory-test"
