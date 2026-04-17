"""
Unit tests for Tutor schema
"""
import pytest
from pydantic import ValidationError
from app.schemas.tutor import (
    TutorMessage,
    TutorRequest,
    TutorResponse,
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
