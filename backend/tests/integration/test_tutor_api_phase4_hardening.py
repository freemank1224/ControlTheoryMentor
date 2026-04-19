"""Phase 4 canary and hardening gates for tutor course-generation contracts."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.content_service import ContentService, InMemoryContentStore
from app.services.learning_service import InMemoryLearningStore, LearningService
from app.services.session_service import FailoverSessionService, InMemorySessionStore, SessionService
from app.services.tutor_service import TutorService, get_tutor_service

from .test_tutor_api import FakeNodeService, FlakyPrimaryStore


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    index = round(0.95 * (len(ordered) - 1))
    return ordered[index]


@pytest.fixture
def app_fixture():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def canary_client():
    from app.api.routes import tutor

    session_service = SessionService(InMemorySessionStore(data={}), backend_name="memory-canary")
    tutor_service = _build_fast_tutor_service(session_service=session_service)

    tutor.conversations.clear()
    app.dependency_overrides[get_tutor_service] = lambda: tutor_service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        tutor.conversations.clear()
        app.dependency_overrides.clear()


def _build_fast_tutor_service(session_service: SessionService | FailoverSessionService) -> TutorService:
    content_service = ContentService(
        store=InMemoryContentStore(artifacts={}, cache_index={}),
        backend_name="content-memory-canary",
    )
    learning_service = LearningService(
        store=InMemoryLearningStore(data={}),
        backend_name="learning-memory-canary",
    )
    return TutorService(
        node_service=FakeNodeService(),
        session_service=session_service,
        content_service=content_service,
        learning_service=learning_service,
    )


def test_phase4_mixed_version_contract_matrix_is_compatible(canary_client: TestClient):
    analyze_cases = [
        (
            "legacy_only",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseType": "problem_solving",
            },
            "problem_solving",
        ),
        (
            "new_manual",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "manual",
                "courseTypeOverride": "problem_solving",
            },
            "problem_solving",
        ),
        (
            "new_override",
            {
                "question": "Given G(s)=1/(s+1), calculate Kp",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "override",
                "courseTypeOverride": "knowledge_learning",
            },
            "knowledge_learning",
        ),
        (
            "mixed_fields",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "manual",
                "courseTypeOverride": "knowledge_learning",
                "courseType": "problem_solving",
            },
            "knowledge_learning",
        ),
    ]

    for case_name, payload, expected in analyze_cases:
        response = canary_client.post("/api/tutor/analyze", json=payload)
        assert response.status_code == 200, f"analyze case={case_name} should not fail"
        assert response.json()["metadata"]["finalCourseType"] == expected

    start_cases = [
        (
            "legacy_only",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseType": "problem_solving",
            },
            "problem_solving",
        ),
        (
            "new_manual",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "manual",
                "courseTypeOverride": "problem_solving",
            },
            "problem_solving",
        ),
        (
            "new_override",
            {
                "question": "Given G(s)=1/(s+1), calculate Kp",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "override",
                "courseTypeOverride": "knowledge_learning",
            },
            "knowledge_learning",
        ),
        (
            "mixed_fields",
            {
                "question": "Explain PID controllers",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "manual",
                "courseTypeOverride": "knowledge_learning",
                "courseType": "problem_solving",
            },
            "knowledge_learning",
        ),
    ]

    for case_name, payload, expected in start_cases:
        response = canary_client.post("/api/tutor/session/start", json=payload)
        assert response.status_code == 200, f"start case={case_name} should not fail"
        body = response.json()
        assert body["metadata"]["finalCourseType"] == expected
        assert body["plan"]["planFinalized"] is True


def test_phase4_mixed_canary_traffic_has_no_blocking_5xx(canary_client: TestClient):
    start_payloads = [
        {
            "question": "Explain PID controllers",
            "pdfId": "graph-task-123",
        },
        {
            "question": "Explain PID controllers",
            "pdfId": "graph-task-123",
            "courseType": "problem_solving",
        },
        {
            "question": "Given G(s)=1/(s+1), calculate Kp",
            "pdfId": "graph-task-123",
            "courseTypeStrategy": "override",
            "courseTypeOverride": "knowledge_learning",
        },
        {
            "question": "How does PID reduce steady-state error?",
            "pdfId": "graph-task-123",
            "courseTypeStrategy": "manual",
            "courseTypeOverride": "problem_solving",
        },
    ]

    status_codes: list[int] = []

    for index in range(12):
        start_response = canary_client.post("/api/tutor/session/start", json=start_payloads[index % len(start_payloads)])
        status_codes.append(start_response.status_code)
        if start_response.status_code != 200:
            continue

        session_id = start_response.json()["sessionId"]

        step_one = canary_client.post(f"/api/tutor/session/{session_id}/next")
        status_codes.append(step_one.status_code)

        step_two = canary_client.post(f"/api/tutor/session/{session_id}/next")
        status_codes.append(step_two.status_code)

        if step_two.status_code == 200 and step_two.json().get("needsUserResponse"):
            respond = canary_client.post(
                f"/api/tutor/session/{session_id}/respond",
                json={"response": "I would inspect the error dynamics and constraints."},
            )
            status_codes.append(respond.status_code)

    blocking_5xx = [code for code in status_codes if code >= 500]
    assert not blocking_5xx, f"found blocking 5xx responses: {blocking_5xx}"


def test_phase4_performance_acceptance_for_core_contract_paths(canary_client: TestClient):
    analyze_latencies: list[float] = []
    start_latencies: list[float] = []

    for _ in range(12):
        started_at = time.perf_counter()
        analyze_response = canary_client.post(
            "/api/tutor/analyze",
            json={
                "question": "How does PID reduce steady-state error?",
                "pdfId": "graph-task-123",
                "courseTypeStrategy": "auto",
            },
        )
        analyze_latencies.append(time.perf_counter() - started_at)
        assert analyze_response.status_code == 200

    for _ in range(8):
        started_at = time.perf_counter()
        start_response = canary_client.post(
            "/api/tutor/session/start",
            json={
                "question": "How does PID reduce steady-state error?",
                "pdfId": "graph-task-123",
                "mode": "interactive",
                "courseTypeStrategy": "manual",
                "courseTypeOverride": "problem_solving",
            },
        )
        start_latencies.append(time.perf_counter() - started_at)
        assert start_response.status_code == 200

    analyze_p95 = _p95(analyze_latencies)
    start_p95 = _p95(start_latencies)
    analyze_avg = sum(analyze_latencies) / len(analyze_latencies)
    start_avg = sum(start_latencies) / len(start_latencies)

    print(
        "Phase4 perf metrics:",
        {
            "analyze_ms_avg": round(analyze_avg * 1000, 2),
            "analyze_ms_p95": round(analyze_p95 * 1000, 2),
            "start_ms_avg": round(start_avg * 1000, 2),
            "start_ms_p95": round(start_p95 * 1000, 2),
        },
    )

    assert analyze_p95 < 0.20, f"analyze p95 too high: {analyze_p95:.4f}s"
    assert start_p95 < 0.35, f"session start p95 too high: {start_p95:.4f}s"


def test_phase4_rollback_drill_fallback_and_failback_keeps_contract(app_fixture):
    from app.api.routes import tutor

    primary = FlakyPrimaryStore()
    failover_service = FailoverSessionService(
        primary_store=primary,
        fallback_store=InMemorySessionStore(data={}),
        healthcheck=primary.ping,
        primary_backend_name="redis-failover-phase4",
    )

    tutor.conversations.clear()
    app_fixture.dependency_overrides[get_tutor_service] = lambda: _build_fast_tutor_service(failover_service)
    try:
        with TestClient(app_fixture) as client:
            started = client.post(
                "/api/tutor/session/start",
                json={
                    "question": "Explain PID controllers",
                    "pdfId": "graph-task-123",
                    "courseTypeStrategy": "manual",
                    "courseTypeOverride": "problem_solving",
                },
            )
            assert started.status_code == 200
            assert started.json()["metadata"]["finalCourseType"] == "problem_solving"
            assert started.json()["metadata"]["store"] == "redis-failover-phase4"
            session_id = started.json()["sessionId"]

            primary.go_down()

            during_outage = client.post(f"/api/tutor/session/{session_id}/next")
            assert during_outage.status_code == 200
            assert during_outage.json()["metadata"]["store"] == "memory-fallback"
            assert during_outage.json()["metadata"]["finalCourseType"] == "problem_solving"

            primary.recover()

            after_recovery = client.get(f"/api/tutor/session/{session_id}")
            assert after_recovery.status_code == 200
            assert after_recovery.json()["metadata"]["store"] == "redis-failover-phase4"
            assert after_recovery.json()["metadata"]["finalCourseType"] == "problem_solving"
            assert after_recovery.json()["plan"]["planFinalized"] is True
    finally:
        tutor.conversations.clear()
        app_fixture.dependency_overrides.clear()
