"""Tests for Graphify Celery task orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from worker.graphify_wrapper import GraphifyConfigurationError
from worker.tasks import cleanup_old_tasks, health_check_task, process_pdf_task


def test_process_pdf_task_run_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    class FakeProcessor:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def process_pdf(self, pdf_path: str, graph_id: str, progress_callback):
            progress_callback(50, "working", {"stage": "semantic_extraction", "currentChunkIndex": 2, "totalChunks": 4})
            return {
                "nodes_count": 4,
                "edges_count": 6,
                "communities_count": 2,
                "files_processed": 1,
                "input_tokens": 123,
                "output_tokens": 45,
                "graph_json_path": "C:/tmp/graph.json",
                "report_path": "C:/tmp/GRAPH_REPORT.md",
                "graphify_version": "0.4.21",
            }

        def close(self):
            return None

    monkeypatch.setattr("worker.tasks.GraphifyProcessor", FakeProcessor)

    updates: list[tuple[str, dict[str, object]]] = []
    fake_task = SimpleNamespace(
        update_state=lambda state, meta: updates.append((state, meta)),
        request=SimpleNamespace(retries=0),
        retry=lambda exc, countdown: (_ for _ in ()).throw(AssertionError("retry should not be called")),
    )

    result = process_pdf_task.run.__func__(fake_task, "task-1", str(pdf_path))

    assert result["status"] == "completed"
    assert result["graph_id"] == "graph-task-1"
    assert result["result"]["input_tokens"] == 123
    assert updates[-1][0] == "PROGRESS"
    assert updates[-1][1]["stage"] == "semantic_extraction"
    assert updates[-1][1]["currentChunkIndex"] == 2


def test_process_pdf_task_run_raises_missing_file(tmp_path: Path) -> None:
    fake_task = SimpleNamespace(
        update_state=lambda state, meta: None,
        request=SimpleNamespace(retries=0),
        retry=lambda exc, countdown: (_ for _ in ()).throw(AssertionError("retry should not be called")),
    )

    with pytest.raises(FileNotFoundError):
        process_pdf_task.run.__func__(fake_task, "task-1", str(tmp_path / "missing.pdf"))


def test_process_pdf_task_run_does_not_retry_configuration_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    class FakeProcessor:
        def __init__(self, **kwargs):
            pass

        def process_pdf(self, pdf_path: str, graph_id: str, progress_callback):
            raise GraphifyConfigurationError("missing provider config")

        def close(self):
            return None

    monkeypatch.setattr("worker.tasks.GraphifyProcessor", FakeProcessor)

    fake_task = SimpleNamespace(
        update_state=lambda state, meta: None,
        request=SimpleNamespace(retries=0),
        retry=lambda exc, countdown: (_ for _ in ()).throw(AssertionError("retry should not be called")),
    )

    with pytest.raises(GraphifyConfigurationError):
        process_pdf_task.run.__func__(fake_task, "task-1", str(pdf_path))


def test_health_check_task_returns_healthy() -> None:
    result = health_check_task.run()
    assert result["status"] == "healthy"


def test_cleanup_old_tasks_returns_completed() -> None:
    result = cleanup_old_tasks.run()
    assert result["status"] == "completed"
