"""Celery tasks for Graphify-backed PDF processing."""

from __future__ import annotations

import logging
import os
from typing import Any

from celery import shared_task

from worker.graphify_wrapper import (
    GraphifyConfigurationError,
    GraphifyProcessor,
    GraphifySemanticExtractionError,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pdf_task(
    self,
    task_id: str,
    pdf_path: str,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "password",
) -> dict[str, Any]:
    """Process a PDF into Graphify artifacts and optional Neo4j state."""
    logger.info("Processing PDF task %s: %s", task_id, pdf_path)

    def report_progress(percent: int, message: str) -> None:
        self.update_state(
            state="PROGRESS",
            meta={
                "task_id": task_id,
                "status": "processing",
                "percent": percent,
                "message": message,
            },
        )

    try:
        report_progress(5, "Initializing Graphify worker...")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        processor = GraphifyProcessor(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
        )

        graph_id = f"graph-{task_id}"
        result = processor.process_pdf(
            pdf_path,
            graph_id=graph_id,
            progress_callback=report_progress,
        )
        processor.close()

        logger.info("Successfully processed PDF task %s", task_id)
        return {
            "status": "completed",
            "task_id": task_id,
            "graph_id": graph_id,
            "percent": 100,
            "message": "Graphify processing completed successfully",
            "result": {
                "nodes_count": result.get("nodes_count", 0),
                "edges_count": result.get("edges_count", 0),
                "communities_count": result.get("communities_count", 0),
                "files_processed": result.get("files_processed", 0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "graph_json_path": result.get("graph_json_path"),
                "report_path": result.get("report_path"),
                "graphify_version": result.get("graphify_version"),
            },
        }
    except (FileNotFoundError, ValueError, GraphifyConfigurationError, GraphifySemanticExtractionError):
        logger.exception("Non-retryable Graphify task failure %s", task_id)
        raise
    except Exception as exc:
        logger.exception("Retryable Graphify task failure %s", task_id)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def health_check_task() -> dict[str, str]:
    """Health check task to verify worker liveness."""
    return {
        "status": "healthy",
        "message": "Worker service is running",
    }


@shared_task
def cleanup_old_tasks() -> dict[str, int | str]:
    """Placeholder cleanup task for future storage retention."""
    logger.info("Running cleanup task for old tasks")
    return {"status": "completed", "cleaned": 0}
