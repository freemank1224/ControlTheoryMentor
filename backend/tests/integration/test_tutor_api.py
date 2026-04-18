"""
Integration tests for Tutor API endpoints
"""
import pytest
from fastapi.testclient import TestClient


class TestTutorChatAPI:
    """Test tutor chat endpoint"""

    def test_tutor_chat_success(self, client: TestClient):
        """Test successful tutor interaction"""
        request_data = {
            "message": "Explain PID controllers",
            "mode": "interactive"
        }

        response = client.post("/api/tutor/chat", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "conversation_id" in data
        assert len(data["message"]) > 0

    def test_tutor_chat_with_context(self, client: TestClient):
        """Test tutor interaction with context"""
        request_data = {
            "message": "What is feedback?",
            "mode": "interactive",
            "context": {
                "current_topic": "control systems",
                "learning_level": "beginner"
            }
        }

        response = client.post("/api/tutor/chat", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "metadata" in data

    def test_tutor_chat_continuation(self, client: TestClient):
        """Test conversation continuation"""
        # First message
        request1 = {
            "message": "What is a transfer function?"
        }
        response1 = client.post("/api/tutor/chat", json=request1)
        conversation_id = response1.json()["conversation_id"]

        # Follow-up message
        request2 = {
            "message": "Can you give me an example?",
            "conversation_id": conversation_id
        }
        response2 = client.post("/api/tutor/chat", json=request2)

        assert response2.status_code == 200
        assert response2.json()["conversation_id"] == conversation_id


class TestTutorSessionAPI:
    """Test step-by-step tutor session endpoints"""

    def test_start_tutor_session_success(self, client: TestClient):
        """Starting a session should return a ready plan"""
        request_data = {
            "question": "Explain PID controllers",
            "pdfId": "graph-task-123",
            "mode": "interactive",
            "context": {
                "learning_level": "beginner"
            }
        }

        response = client.post("/api/tutor/session/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"].startswith("session-")
        assert data["status"] == "ready"
        assert data["currentStep"] is None
        assert len(data["plan"]["steps"]) == 4
        assert data["metadata"]["pdfId"] == "graph-task-123"

    def test_tutor_session_next_and_respond_flow(self, client: TestClient):
        """A session should advance, require responses, and continue after feedback"""
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "Explain transfer function",
                "pdfId": "graph-task-456"
            }
        )
        session_id = start_response.json()["sessionId"]

        first_step = client.post(f"/api/tutor/session/{session_id}/next")
        assert first_step.status_code == 200
        assert first_step.json()["currentStep"]["id"] == "step-1"
        assert first_step.json()["needsUserResponse"] is False

        second_step = client.post(f"/api/tutor/session/{session_id}/next")
        assert second_step.status_code == 200
        second_data = second_step.json()
        assert second_data["currentStep"]["id"] == "step-2"
        assert second_data["status"] == "awaiting_response"
        assert second_data["needsUserResponse"] is True

        blocked = client.post(f"/api/tutor/session/{session_id}/next")
        assert blocked.status_code == 409

        respond = client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={
                "response": "A transfer function maps input to output in the Laplace domain."
            }
        )
        assert respond.status_code == 200
        respond_data = respond.json()
        assert respond_data["status"] == "ready"
        assert respond_data["needsUserResponse"] is False
        assert respond_data["feedback"] is not None

    def test_tutor_session_can_complete(self, client: TestClient):
        """A session should reach the completed state after all steps are handled"""
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "How does feedback affect stability?",
                "pdfId": "graph-task-789"
            }
        )
        session_id = start_response.json()["sessionId"]

        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "Feedback can improve robustness and reduce steady-state error."},
        )
        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "I would inspect whether the feedback loop changes pole locations."},
        )
        final_step = client.post(f"/api/tutor/session/{session_id}/next")

        assert final_step.status_code == 200
        final_data = final_step.json()
        assert final_data["currentStep"]["id"] == "step-4"

        completed = client.post(f"/api/tutor/session/{session_id}/next")
        assert completed.status_code == 200
        completed_data = completed.json()
        assert completed_data["status"] == "completed"
        assert completed_data["canAdvance"] is False

    def test_respond_without_active_interactive_step_fails(self, client: TestClient):
        """Responding before an interactive step is active should fail"""
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "Explain root locus",
                "pdfId": "graph-task-101"
            }
        )
        session_id = start_response.json()["sessionId"]

        response = client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "It tracks pole movement."},
        )

        assert response.status_code == 409


class TestQuizAPI:
    """Test quiz generation endpoint"""

    def test_generate_quiz_success(self, client: TestClient):
        """Test successful quiz generation"""
        request_data = {
            "topic": "PID Controllers",
            "difficulty": "medium",
            "question_count": 3
        }

        response = client.post("/api/tutor/quiz", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "quiz_id" in data
        assert "questions" in data
        assert len(data["questions"]) == 3

    def test_generate_quiz_custom_types(self, client: TestClient):
        """Test quiz generation with custom question types"""
        request_data = {
            "topic": "Control Systems",
            "difficulty": "easy",
            "question_count": 5,
            "question_types": ["multiple_choice", "true_false"]
        }

        response = client.post("/api/tutor/quiz", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) == 5


class TestProblemSolvingAPI:
    """Test problem-solving endpoint"""

    def test_problem_solving_success(self, client: TestClient):
        """Test successful problem-solving help"""
        request_data = {
            "problem_statement": "Design a PID controller for a system with transfer function G(s) = 1/(s+1)",
            "subject": "control systems",
            "hints_requested": 2
        }

        response = client.post("/api/tutor/solve", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "solution_steps" in data
        assert "hints" in data
        assert "explanation" in data
        assert len(data["solution_steps"]) > 0

    def test_problem_solving_no_hints(self, client: TestClient):
        """Test problem-solving without hints"""
        request_data = {
            "problem_statement": "Explain stability criteria",
            "subject": "control systems",
            "hints_requested": 0
        }

        response = client.post("/api/tutor/solve", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert len(data["hints"]) == 0


class TestConversationAPI:
    """Test conversation management endpoints"""

    def test_get_conversation_history(self, client: TestClient):
        """Test getting conversation history"""
        # First create a conversation
        request = {
            "message": "Hello"
        }
        response = client.post("/api/tutor/chat", json=request)
        conversation_id = response.json()["conversation_id"]

        # Get history
        history_response = client.get(f"/api/tutor/conversations/{conversation_id}")

        assert history_response.status_code == 200
        data = history_response.json()
        assert "messages" in data

    def test_get_nonexistent_conversation(self, client: TestClient):
        """Test getting non-existent conversation"""
        response = client.get("/api/tutor/conversations/nonexistent")

        assert response.status_code == 404


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_tutor_state():
    """Reset in-memory tutor state between tests"""
    from app.api.routes import tutor

    tutor.conversations.clear()
    tutor.tutor_sessions.clear()
    yield
    tutor.conversations.clear()
    tutor.tutor_sessions.clear()
