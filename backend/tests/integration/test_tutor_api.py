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
