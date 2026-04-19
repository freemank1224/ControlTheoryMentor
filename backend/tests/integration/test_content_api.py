"""Integration tests for Content API endpoints."""

from fastapi.testclient import TestClient

from app.services.content_service import ContentService, InMemoryContentStore, get_content_service


def build_request_payload() -> dict:
    return {
        "contentRequest": {
            "stage": "concept",
            "stepId": "step-2",
            "stepTitle": "拆解核心概念",
            "objective": "将概念拆成更适合理解检查的子点。",
            "question": "How does PID reduce steady-state error?",
            "graphId": "graph-task-123",
            "sessionMode": "interactive",
            "learnerLevel": "intermediate",
            "responseMode": "interactive",
            "primaryConceptId": "concept-pid",
            "conceptIds": ["concept-pid", "concept-feedback"],
            "highlightedNodeIds": ["concept-pid"],
            "evidencePassageIds": ["chunk-pid-1"],
            "targetContentTypes": ["markdown", "mermaid", "latex", "image", "comic", "animation"],
            "renderHint": "markdown",
        },
        "generationParams": {
            "style": "blueprint",
            "detail": "high",
            "pace": "normal",
            "attempt": 1,
            "imageTimeoutMs": 1500,
        },
    }


def build_interactive_payload() -> dict:
    payload = build_request_payload()
    payload["interactionMode"] = "guided"
    payload["contentRequest"]["targetContentTypes"] = ["markdown", "interactive"]
    return payload


class TestContentAPI:
    """Validate content generation and retrieval APIs."""

    def test_content_generate_and_fetch_flow(self):
        from app.main import app

        def fake_image_fetcher(prompt: str, timeout_ms: int):
            return "image/png", b"\x89PNG\r\n\x1a\n"

        content_service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
            image_fetcher=fake_image_fetcher,
        )
        app.dependency_overrides[get_content_service] = lambda: content_service
        try:
            with TestClient(app) as client:
                generated = client.post("/api/content/generate", json=build_request_payload())
                assert generated.status_code == 200
                generated_data = generated.json()
                assert generated_data["cacheHit"] is False
                artifact = generated_data["artifact"]
                assert artifact["markdown"]
                assert artifact["mermaid"]
                assert artifact["latex"]
                assert artifact["image"] is not None
                assert artifact["comic"] is not None
                assert artifact["animation"] is not None

                artifact_id = artifact["id"]
                fetched = client.get(f"/api/content/{artifact_id}")
                assert fetched.status_code == 200
                assert fetched.json()["artifact"]["id"] == artifact_id

                mermaid = client.get(f"/api/content/{artifact_id}/mermaid")
                assert mermaid.status_code == 200
                assert mermaid.json()["type"] == "mermaid"

                latex = client.get(f"/api/content/{artifact_id}/latex")
                assert latex.status_code == 200
                assert latex.json()["type"] == "latex"

                cached = client.post("/api/content/generate", json=build_request_payload())
                assert cached.status_code == 200
                assert cached.json()["cacheHit"] is True
        finally:
            app.dependency_overrides.clear()

    def test_content_generate_degrades_when_image_fails(self):
        from app.main import app

        def failing_image_fetcher(prompt: str, timeout_ms: int):
            raise TimeoutError("simulated timeout")

        content_service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
            image_fetcher=failing_image_fetcher,
        )
        app.dependency_overrides[get_content_service] = lambda: content_service
        try:
            with TestClient(app) as client:
                payload = build_request_payload()
                payload["contentRequest"]["targetContentTypes"] = ["image"]
                payload["contentRequest"]["renderHint"] = "image"
                generated = client.post("/api/content/generate", json=payload)

                assert generated.status_code == 200
                artifact = generated.json()["artifact"]
                assert artifact["image"]["source"] == "fallback"
                assert artifact["renderHint"] == "markdown"
                assert artifact["markdown"] is not None
        finally:
            app.dependency_overrides.clear()

    def test_content_interactive_endpoint_returns_placeholder_payload(self):
        from app.main import app

        content_service = ContentService(
            store=InMemoryContentStore(artifacts={}, cache_index={}),
            backend_name="memory-test",
        )
        app.dependency_overrides[get_content_service] = lambda: content_service
        try:
            with TestClient(app) as client:
                response = client.post("/api/content/interactive", json=build_interactive_payload())
                assert response.status_code == 200
                artifact = response.json()["artifact"]
                assert artifact["interactive"] is not None
                assert artifact["interactive"]["status"] == "placeholder"
        finally:
            app.dependency_overrides.clear()
