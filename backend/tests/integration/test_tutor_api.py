"""Integration tests for Tutor API endpoints."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import RedisError

from app.schemas.learning import LearningEventType, LearningTrackRequest
from app.schemas.tutor import TutorMode
from app.services.learning_service import InMemoryLearningStore, LearningService, get_learning_service
from app.services.session_service import FailoverSessionService, InMemorySessionStore, RedisSessionStore, SessionService
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


class FlakyPrimaryStore:
    """Primary session store stub used to simulate transient Redis outages in API tests."""

    def __init__(self) -> None:
        self.store = InMemorySessionStore(data={})
        self.available = True

    def save(self, session_id: str, payload: dict):
        self._ensure_available()
        self.store.save(session_id, payload)

    def get(self, session_id: str):
        self._ensure_available()
        return self.store.get(session_id)

    def list(self, limit: int = 50):
        self._ensure_available()
        return self.store.list(limit=limit)

    def ping(self) -> None:
        self._ensure_available()

    def go_down(self) -> None:
        self.available = False

    def recover(self) -> None:
        self.available = True

    def _ensure_available(self) -> None:
        if not self.available:
            raise RedisError("redis temporarily unavailable")


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


@pytest.fixture
def app():
    from app.main import app as fastapi_app

    return fastapi_app


def build_tutor_service(
    session_service: SessionService,
    learning_service: LearningService | None = None,
) -> TutorService:
    return TutorService(
        node_service=FakeNodeService(),
        session_service=session_service,
        learning_service=learning_service,
    )


def cleanup_redis_namespace(client: Redis, prefix: str, index_key: str) -> None:
    keys = list(client.scan_iter(match=f"{prefix}:*"))
    if keys:
        client.delete(*keys)
    client.delete(index_key)


@pytest.fixture
def redis_session_service():
    redis_url = os.getenv("TEST_REDIS_URL") or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    client = Redis.from_url(redis_url, decode_responses=True)
    try:
        client.ping()
    except RedisError as exc:
        pytest.skip(f"Real Redis is not available for tutor recovery integration tests: {exc}")

    namespace = uuid.uuid4().hex
    prefix = f"test:tutor:session:{namespace}"
    index_key = f"test:tutor:sessions:{namespace}"
    cleanup_redis_namespace(client, prefix, index_key)
    try:
        yield SessionService(RedisSessionStore(client, prefix=prefix, index_key=index_key), backend_name="redis-test")
    finally:
        cleanup_redis_namespace(client, prefix, index_key)
        client.close()


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

    def test_session_start_includes_learning_personalization_snapshot(self, app):
        learning_service = LearningService(
            store=InMemoryLearningStore(data={}),
            backend_name="memory-learning-test",
        )
        learning_service.track_event(
            LearningTrackRequest(
                learnerId="learner-7",
                graphId="graph-task-123",
                conceptId="concept-feedback",
                eventType=LearningEventType.STEP_RESPONSE,
                masteryDelta=0.1,
            )
        )
        session_service = SessionService(InMemorySessionStore(data={}), backend_name="memory-test")
        tutor_service = build_tutor_service(session_service=session_service, learning_service=learning_service)

        app.dependency_overrides[get_tutor_service] = lambda: tutor_service
        app.dependency_overrides[get_learning_service] = lambda: learning_service
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/tutor/session/start",
                    json={
                        "question": "Explain PID controllers",
                        "pdfId": "graph-task-123",
                        "learnerId": "learner-7",
                        "mode": "interactive",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                personalization = data["metadata"]["learningSnapshot"]
                assert "pendingReviewConceptIds" in personalization
                assert "concept-feedback" in personalization["pendingReviewConceptIds"]
                assert data["metadata"]["learnerId"] == "learner-7"

                progress = learning_service.get_progress("learner-7", "graph-task-123")
                assert progress.eventCount >= 2
        finally:
            app.dependency_overrides.clear()

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
        intro_request = data["plan"]["steps"][0]["content"]["contentRequest"]
        assert intro_request["stepId"] == "step-1"
        assert intro_request["graphId"] == "graph-task-123"
        assert intro_request["sessionMode"] == "interactive"
        assert intro_request["responseMode"] == "passive"
        assert intro_request["targetContentTypes"] == ["markdown"]
        assert data["plan"]["steps"][0]["content"]["contentArtifactId"].startswith("content-")
        assert data["plan"]["steps"][0]["content"]["contentArtifactStatus"] == "ready"

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

    def test_session_recovery_with_real_redis(self, app, redis_session_service: SessionService):
        first_service = build_tutor_service(redis_session_service)
        app.dependency_overrides[get_tutor_service] = lambda: first_service
        try:
            with TestClient(app) as first_client:
                start_response = first_client.post(
                    "/api/tutor/session/start",
                    json={
                        "question": "How does PID reduce steady-state error?",
                        "pdfId": "graph-task-123",
                        "mode": "interactive",
                        "context": {"learning_level": "beginner"},
                    },
                )
                assert start_response.status_code == 200
                session_id = start_response.json()["sessionId"]

                first_client.post(f"/api/tutor/session/{session_id}/next")
                step_two = first_client.post(f"/api/tutor/session/{session_id}/next")
                assert step_two.status_code == 200
                assert step_two.json()["currentStep"]["id"] == "step-2"
                assert step_two.json()["needsUserResponse"] is True

            recovered_service = build_tutor_service(redis_session_service)
            app.dependency_overrides[get_tutor_service] = lambda: recovered_service

            with TestClient(app) as recovered_client:
                recovered = recovered_client.get(f"/api/tutor/session/{session_id}")
                assert recovered.status_code == 200
                recovered_data = recovered.json()
                assert recovered_data["currentStep"]["id"] == "step-2"
                assert recovered_data["status"] == "awaiting_response"
                assert recovered_data["needsUserResponse"] is True
                assert recovered_data["metadata"]["store"] == "redis-test"

                listed = recovered_client.get("/api/tutor/sessions")
                assert listed.status_code == 200
                listed_data = listed.json()
                assert listed_data["total"] == 1
                assert listed_data["items"][0]["sessionId"] == session_id

                responded = recovered_client.post(
                    f"/api/tutor/session/{session_id}/respond",
                    json={"response": "Integral action accumulates error and removes offset."},
                )
                assert responded.status_code == 200
                assert responded.json()["status"] == "ready"
        finally:
            app.dependency_overrides.clear()

    def test_session_falls_back_and_fails_back_after_transient_redis_outage(self, app):
        primary = FlakyPrimaryStore()
        failover_service = FailoverSessionService(
            primary_store=primary,
            fallback_store=InMemorySessionStore(data={}),
            healthcheck=primary.ping,
            primary_backend_name="redis-failover-test",
        )
        app.dependency_overrides[get_tutor_service] = lambda: build_tutor_service(failover_service)
        try:
            with TestClient(app) as client:
                started = client.post(
                    "/api/tutor/session/start",
                    json={
                        "question": "How does PID reduce steady-state error?",
                        "pdfId": "graph-task-123",
                        "mode": "interactive",
                        "context": {"learning_level": "beginner"},
                    },
                )
                assert started.status_code == 200
                session_id = started.json()["sessionId"]
                assert started.json()["metadata"]["store"] == "redis-failover-test"

                primary.go_down()

                step_one = client.post(f"/api/tutor/session/{session_id}/next")
                assert step_one.status_code == 200
                step_one_data = step_one.json()
                assert step_one_data["currentStep"]["id"] == "step-1"
                assert step_one_data["metadata"]["store"] == "memory-fallback"

                listed_during_outage = client.get("/api/tutor/sessions")
                assert listed_during_outage.status_code == 200
                assert listed_during_outage.json()["metadata"]["store"] == "memory-fallback"
                assert listed_during_outage.json()["items"][0]["sessionId"] == session_id

                primary.recover()

                recovered = client.get(f"/api/tutor/session/{session_id}")
                assert recovered.status_code == 200
                recovered_data = recovered.json()
                assert recovered_data["currentStep"]["id"] == "step-1"
                assert recovered_data["metadata"]["store"] == "redis-failover-test"

                step_two = client.post(f"/api/tutor/session/{session_id}/next")
                assert step_two.status_code == 200
                assert step_two.json()["currentStep"]["id"] == "step-2"
                assert step_two.json()["metadata"]["store"] == "redis-failover-test"
        finally:
            app.dependency_overrides.clear()


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
