"""
Celery tasks for background processing
"""
from celery import shared_task
from worker.graphify_wrapper import GraphifyProcessor
from worker.celery_app import celery_app
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pdf_task(
    self,
    task_id: str,
    pdf_path: str,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "password"
) -> Dict[str, Any]:
    """
    Process a PDF file and generate knowledge graph

    This task runs in the background using Celery and:
    1. Reads the PDF file
    2. Extracts concepts and relationships
    3. Generates knowledge graph data
    4. Stores results in Neo4j

    Args:
        task_id: Unique task identifier
        pdf_path: Path to the PDF file
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password

    Returns:
        Dictionary containing processing results

    Raises:
        Exception: If processing fails, will retry up to 3 times
    """
    logger.info(f"Processing PDF task {task_id}: {pdf_path}")

    try:
        # Update task status
        self.update_state(
            state='PROGRESS',
            meta={
                'task_id': task_id,
                'status': 'processing',
                'percent': 10,
                'message': 'Initializing PDF processor...'
            }
        )

        # Validate PDF file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Initialize processor
        processor = GraphifyProcessor(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'task_id': task_id,
                'status': 'processing',
                'percent': 30,
                'message': 'Extracting text from PDF...'
            }
        )

        # Process PDF
        result = processor.process_pdf(pdf_path, task_id)

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'task_id': task_id,
                'status': 'processing',
                'percent': 70,
                'message': 'Generating knowledge graph...'
            }
        )

        # Close processor connection
        processor.close()

        # Final progress update
        self.update_state(
            state='PROGRESS',
            meta={
                'task_id': task_id,
                'status': 'processing',
                'percent': 90,
                'message': 'Finalizing...'
            }
        )

        logger.info(f"Successfully processed PDF task {task_id}")

        return {
            'status': 'completed',
            'task_id': task_id,
            'graph_id': task_id,
            'percent': 100,
            'message': 'PDF processing completed successfully',
            'result': {
                'nodes_count': len(result.get('nodes', [])),
                'edges_count': len(result.get('edges', [])),
                'formulas_count': len(result.get('formulas', [])),
            }
        }

    except FileNotFoundError as e:
        logger.error(f"File not found in task {task_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing PDF task {task_id}: {e}")

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task
def generate_graph_task(
    pdf_id: str,
    text_content: str,
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "password"
) -> Dict[str, Any]:
    """
    Generate knowledge graph from extracted text content

    Args:
        pdf_id: PDF identifier
        text_content: Extracted text content
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password

    Returns:
        Dictionary containing graph generation results
    """
    logger.info(f"Generating graph for PDF {pdf_id}")

    try:
        # Import here to avoid circular dependencies
        from worker.graphify_wrapper import extract_entities_from_text

        # Extract entities from text
        result = extract_entities_from_text(text_content)

        # Store in Neo4j
        processor = GraphifyProcessor(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )

        if processor.driver:
            with processor.driver.session() as session:
                processor._save_to_neo4j(session, result, pdf_id)

            processor.close()

        logger.info(f"Successfully generated graph for PDF {pdf_id}")

        return {
            'status': 'completed',
            'pdf_id': pdf_id,
            'graph_id': pdf_id,
            'result': {
                'nodes_count': len(result.get('nodes', [])),
                'edges_count': len(result.get('edges', [])),
            }
        }

    except Exception as e:
        logger.error(f"Error generating graph for PDF {pdf_id}: {e}")
        raise


@shared_task
def health_check_task() -> Dict[str, str]:
    """
    Health check task to verify worker is functioning

    Returns:
        Dictionary with health status
    """
    return {
        'status': 'healthy',
        'message': 'Worker service is running'
    }


# Task registration for Celery Beat (optional scheduling)
@shared_task
def cleanup_old_tasks():
    """
    Clean up old completed tasks from storage
    """
    logger.info("Running cleanup task for old tasks")
    # Implementation would depend on storage backend
    return {'status': 'completed', 'cleaned': 0}
