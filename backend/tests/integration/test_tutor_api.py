"""Integration tests for Tutor API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.schemas.tutor import TutorMode
from app.services.session_service import InMemorySessionStore, SessionService
from app.services.tutor_service import TutorService, get_tutor_service


class FakeNodeService:
    """Deterministic graph lookup service for tutor API integration tests."""

    def semantic_search(self, graph_id: str, query: str, limit: int = 10):
        items = [
            {
                "graphId": graph_id,
                "id": "concept-pid",
                "label": "PID Controller",
                "nodeType": "concept",
                "fileType": "pdf",
                "community": 1,
                "sourceFile": "chapter-3.pdf",
                "sourceLocation": "p.12",
                "properties": {"kind": "controller"},
                "score": 0.98,
                "matchReason": "keyword_overlap:2",
            },
            {
                "graphId": graph_id,
                "id": "concept-feedback",
                "label": "Feedback Loop",
                "nodeType": "concept",
                "fileType": "pdf",
                "community": 2,
                "sourceFile": "chapter-2.pdf",
                "sourceLocation": "p.8",
                "properties": {"kind": "structure"},
                "score": 0.74,
                "matchReason": "keyword_overlap:1",
            },
        ]
        return {
            "graphId": graph_id,
            "query": query,
            "items": items[:limit],
            "metadata": {"mode": "semantic"},
        }

    def get_concept_context(self, graph_id: str, node_id: str):
        payloads = {
            "concept-pid": {
                "graphId": graph_id,
                "concept": {
                    "graphId": graph_id,
                    "id": "concept-pid",
                    "label": "PID Controller",
                    "nodeType": "concept",
                    "fileType": "pdf",
                    "community": 1,
                    "sourceFile": "chapter-3.pdf",
                    "sourceLocation": "p.12",
                    "properties": {},
                    "score": 0.98,
                    "matchReason": "keyword_overlap:2",
                },
                "prerequisites": [{"id": "concept-feedback"}],
                "relatedNodes": [{"id": "concept-stability"}, {"id": "concept-tuning"}],
                "formulas": [{"id": "formula-pid"}],
                "examples": [{"id": "example-motor-speed"}],
                "sourceSections": [],
                "passages": [
                    {
                        "chunkId": "chunk-pid-1",
                        "sourceFile": "chapter-3.pdf",
                        "sourceLocation": "p.12",
                        "pageStart": 12,
                        "pageEnd": 12,
                        "text": "A PID controller combines proportional, integral, and derivative actions. The proportional term reacts to present error. Integral action removes steady-state error.",
                    },
                    {
                        "chunkId": "chunk-pid-2",
                        "sourceFile": "chapter-3.pdf",
                        "sourceLocation": "p.13",
                        "pageStart": 13,
                        "pageEnd": 13,
                        "text": "Derivative action anticipates error changes and can improve damping in transient response.",
                    },
                ],
                "lookup": {},
                "metadata": {"passageCount": 2},
            },
            "concept-feedback": {
                "graphId": graph_id,
                "concept": {
                    "graphId": graph_id,
                    "id": "concept-feedback",
                    "label": "Feedback Loop",
                    "nodeType": "concept",
                    "fileType": "pdf",
                    "community": 2,
                    "sourceFile": "chapter-2.pdf",
                    "sourceLocation": "p.8",
                    "properties": {},
                    "score": 0.74,
                    "matchReason": "keyword_overlap:1",
                },
                "prerequisites": [],
                "relatedNodes": [{"id": "concept-stability"}],
                "formulas": [],
                "examples": [],
                "sourceSections": [],
                "passages": [
                    {
                        "chunkId": "chunk-feedback-1",
                        "sourceFile": "chapter-2.pdf",
                        "sourceLocation": "p.8",
                        "pageStart": 8,
                        "pageEnd": 8,
                        "text": "Feedback compares output against the reference input and drives the error toward zero.",
                    }
                ],
                "lookup": {},
                "metadata": {"passageCount": 1},
            },
        }
        return payloads[node_id]


@pytest.fixture
def client():
    """Create test client with a deterministic TutorService override."""
    from app.main import app

    session_service = SessionService(InMemorySessionStore(data={}), backend_name="memory-test")
    tutor_service = TutorService(node_service=FakeNodeService(), session_service=session_service)
    app.dependency_overrides[get_tutor_service] = lambda: tutor_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_tutor_state():
    """Reset lightweight chat state between tests."""
    from app.api.routes import tutor

    tutor.conversations.clear()
    yield
    tutor.conversations.clear()


class TestTutorAnalyzeAPI:
    """Test graph-grounded tutor analysis endpoint."""

    def test_tutor_analyze_returns_evidence_rankings(self, client: TestClient):
        response = client.post(
            "/api/tutor/analyze",
            json={
                "question": "How does PID reduce steady-state error?",
                "pdfId": "graph-task-123",
                "mode": "interactive",
                "context": {"learning_level": "beginner"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["graphId"] == "graph-task-123"
        assert data["relevantConcepts"][0]["node"]["id"] == "concept-pid"
        assert data["evidencePassages"][0]["chunkId"] == "chunk-pid-1"
        assert "steady-state error" in data["evidencePassages"][0]["excerpt"].lower()
        assert data["suggestedSession"]["sessionStore"] == "memory-test"


class TestTutorSessionAPI:
    """Test service-backed tutor session endpoints."""

    def test_start_session_returns_plan_with_analysis(self, client: TestClient):
        response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "mode": "interactive",
                "context": {"learning_level": "beginner"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"].startswith("session-")
        assert data["status"] == "ready"
        assert len(data["plan"]["steps"]) == 4
        assert data["metadata"]["analysis"]["highlightedNodeIds"][0] == "concept-pid"
        assert data["metadata"]["store"] == "memory-test"

    def test_list_sessions_back_jump_and_respond_flow(self, client: TestClient):
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "How does PID reduce steady-state error?",
                "pdfId": "graph-task-123",
                "mode": "interactive",
            },
        )
        session_id = start_response.json()["sessionId"]

        sessions = client.get("/api/tutor/sessions")
        assert sessions.status_code == 200
        sessions_data = sessions.json()
        assert sessions_data["total"] == 1
        assert sessions_data["items"][0]["sessionId"] == session_id

        step_one = client.post(f"/api/tutor/session/{session_id}/next")
        assert step_one.status_code == 200
        assert step_one.json()["currentStep"]["id"] == "step-1"

        step_two = client.post(f"/api/tutor/session/{session_id}/next")
        assert step_two.status_code == 200
        assert step_two.json()["currentStep"]["id"] == "step-2"
        assert step_two.json()["needsUserResponse"] is True

        back = client.post(f"/api/tutor/session/{session_id}/back")
        assert back.status_code == 200
        assert back.json()["currentStep"]["id"] == "step-1"
        assert back.json()["feedback"] == "Moved back to the previous step."

        jump = client.post(
            f"/api/tutor/session/{session_id}/jump",
            json={"stepId": "step-3"},
        )
        assert jump.status_code == 200
        jump_data = jump.json()
        assert jump_data["currentStep"]["id"] == "step-3"
        assert jump_data["needsUserResponse"] is True

        respond = client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "I would track the error signal and inspect the integral term."},
        )
        assert respond.status_code == 200
        respond_data = respond.json()
        assert respond_data["status"] == "ready"
        assert respond_data["feedback"] is not None

    def test_session_can_complete(self, client: TestClient):
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "How does feedback affect stability?",
                "pdfId": "graph-task-123",
                "mode": "problem_solving",
            },
        )
        session_id = start_response.json()["sessionId"]

        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "Feedback changes the closed-loop poles and can improve robustness."},
        )
        client.post(f"/api/tutor/session/{session_id}/next")
        client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "I would identify the plant, the loop gain, and the target damping ratio."},
        )
        final_step = client.post(f"/api/tutor/session/{session_id}/next")
        assert final_step.status_code == 200
        assert final_step.json()["currentStep"]["id"] == "step-4"

        completed = client.post(f"/api/tutor/session/{session_id}/next")
        assert completed.status_code == 200
        completed_data = completed.json()
        assert completed_data["status"] == "completed"
        assert completed_data["canAdvance"] is False

    def test_respond_without_active_interactive_step_fails(self, client: TestClient):
        start_response = client.post(
            "/api/tutor/session/start",
            json={
                "question": "Explain root locus",
                "pdfId": "graph-task-123",
            },
        )
        session_id = start_response.json()["sessionId"]

        response = client.post(
            f"/api/tutor/session/{session_id}/respond",
            json={"response": "It tracks pole movement."},
        )

        assert response.status_code == 409


class TestQuizAPI:
    """Test quiz generation endpoint."""

    def test_generate_quiz_success(self, client: TestClient):
        response = client.post(
            "/api/tutor/quiz",
            json={
                "topic": "PID Controllers",
                "difficulty": "medium",
                "question_count": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "quiz_id" in data
        assert len(data["questions"]) == 3


class TestProblemSolvingAPI:
    """Test problem-solving endpoint."""

    def test_problem_solving_success(self, client: TestClient):
        response = client.post(
            "/api/tutor/solve",
            json={
                "problem_statement": "Design a PID controller for G(s) = 1/(s+1)",
                "subject": "control systems",
                "hints_requested": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["solution_steps"]) > 0
        assert len(data["hints"]) == 2


class TestConversationAPI:
    """Test lightweight conversation management endpoints."""

    def test_get_conversation_history(self, client: TestClient):
        response = client.post("/api/tutor/chat", json={"message": "Hello", "mode": TutorMode.INTERACTIVE.value})
        conversation_id = response.json()["conversation_id"]

        history_response = client.get(f"/api/tutor/conversations/{conversation_id}")

        assert history_response.status_code == 200
        assert "messages" in history_response.json()

    def test_get_nonexistent_conversation(self, client: TestClient):
        response = client.get("/api/tutor/conversations/nonexistent")
        assert response.status_code == 404
