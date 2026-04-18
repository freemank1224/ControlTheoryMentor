"""
Unit tests for Tutor schema
"""
import pytest
from pydantic import ValidationError
from app.schemas.tutor import (
    TeachingPlan,
    TeachingStep,
    TeachingStepType,
    TutorMessage,
    TutorRequest,
    TutorResponse,
    TutorSessionRespondRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionStatus,
    MessageType,
    TutorMode
)


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
            content={"markdown": "先建立背景"}
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
