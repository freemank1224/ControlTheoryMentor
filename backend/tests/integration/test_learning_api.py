"""Integration tests for Learning API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.schemas.learning import FeedbackDifficulty
from app.services.learning_service import InMemoryLearningStore, LearningService, get_learning_service


class TestLearningAPI:
    """Validate learning tracking, progress read, and feedback submission APIs."""

    def test_track_progress_feedback_flow(self):
        from app.main import app

        learning_service = LearningService(store=InMemoryLearningStore(data={}), backend_name="memory-test")
        app.dependency_overrides[get_learning_service] = lambda: learning_service
        try:
            with TestClient(app) as client:
                tracked = client.post(
                    "/api/learning/track",
                    json={
                        "learnerId": "learner-42",
                        "graphId": "graph-task-123",
                        "sessionId": "session-abc",
                        "stepId": "step-2",
                        "conceptId": "concept-pid",
                        "eventType": "step_response",
                        "confidence": 0.9,
                        "metadata": {"source": "tutor"},
                    },
                )
                assert tracked.status_code == 200
                tracked_data = tracked.json()
                assert tracked_data["progress"]["eventCount"] == 1
                assert tracked_data["progress"]["metadata"]["store"] == "memory-test"

                progress = client.get(
                    "/api/learning/progress",
                    params={"learnerId": "learner-42", "graphId": "graph-task-123"},
                )
                assert progress.status_code == 200
                progress_data = progress.json()["progress"]
                assert progress_data["sessionId"] == "session-abc"
                assert progress_data["currentStepId"] == "step-2"

                feedback = client.post(
                    "/api/learning/feedback",
                    json={
                        "learnerId": "learner-42",
                        "graphId": "graph-task-123",
                        "sessionId": "session-abc",
                        "stepId": "step-2",
                        "conceptId": "concept-pid",
                        "rating": 4,
                        "difficulty": FeedbackDifficulty.APPROPRIATE.value,
                        "comment": "Good pacing.",
                    },
                )
                assert feedback.status_code == 200
                feedback_data = feedback.json()
                assert feedback_data["feedback"]["rating"] == 4
                assert feedback_data["progress"]["feedbackCount"] == 1
                assert feedback_data["progress"]["averageFeedbackRating"] == 4.0
        finally:
            app.dependency_overrides.clear()

    def test_progress_returns_empty_snapshot_for_new_learner(self):
        from app.main import app

        learning_service = LearningService(store=InMemoryLearningStore(data={}), backend_name="memory-test")
        app.dependency_overrides[get_learning_service] = lambda: learning_service
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/learning/progress",
                    params={"learnerId": "new-learner", "graphId": "graph-task-123"},
                )
                assert response.status_code == 200
                progress = response.json()["progress"]
                assert progress["eventCount"] == 0
                assert progress["feedbackCount"] == 0
                assert progress["conceptMastery"] == []
        finally:
            app.dependency_overrides.clear()
