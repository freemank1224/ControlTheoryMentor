"""PDF API routes for upload and background Graphify processing."""
import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
from celery.result import AsyncResult

from app.schemas.pdf import (
    PDFUploadResponse,
    PDFParseRequest,
    PDFParseResponse,
    PDFStatus,
    ParseStatus
)
from app.config import settings
from app.celery_client import get_celery_app, TASK_PROCESS_PDF

router = APIRouter(prefix="/pdf", tags=["PDF"])

# In-memory storage for demo purposes
pdf_storage = {}

celery_app = get_celery_app()


def _map_task_state(task_result: AsyncResult) -> PDFStatus:
    if task_result.state == "SUCCESS":
        return PDFStatus.COMPLETED
    if task_result.state in {"PROGRESS", "STARTED", "RETRY"}:
        return PDFStatus.PARSING
    if task_result.state == "FAILURE":
        return PDFStatus.FAILED
    return PDFStatus.UPLOADED


@router.post("/upload", response_model=PDFUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file for processing

    - **file**: PDF file to upload
    - Returns PDF metadata including task ID for background processing
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")

    # Validate file size
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

    # Create PDF storage directory if it doesn't exist
    pdf_dir = Path(settings.PDF_STORAGE_PATH)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique ID
    task_id = f"task-{uuid.uuid4()}"
    pdf_id = f"pdf-{uuid.uuid4()}"

    # Save file
    file_path = pdf_dir / f"{pdf_id}.pdf"
    with open(file_path, "wb") as f:
        f.write(content)

    # Page count is resolved during worker-side Graphify processing.
    page_count = 1

    # Store metadata
    pdf_storage[pdf_id] = {
        "id": pdf_id,
        "task_id": task_id,
        "filename": file.filename,
        "page_count": page_count,
        "status": PDFStatus.UPLOADED,
        "file_path": str(file_path)
    }

    try:
        celery_app.send_task(
            TASK_PROCESS_PDF,
            kwargs={
                "task_id": task_id,
                "pdf_path": str(file_path),
                "neo4j_uri": settings.NEO4J_URI,
                "neo4j_user": settings.NEO4J_USER,
                "neo4j_password": settings.NEO4J_PASSWORD,
            },
            task_id=task_id,
        )
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        pdf_storage.pop(pdf_id, None)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to enqueue Graphify processing task: {exc}",
        ) from exc

    return PDFUploadResponse(
        id=pdf_id,
        taskId=task_id,
        filename=file.filename,
        page_count=page_count,
        status=PDFStatus.UPLOADED
    )


@router.post("/parse", response_model=PDFParseResponse)
async def parse_pdf(request: PDFParseRequest):
    """
    Parse a PDF and extract text, images, and tables

    - **pdf_id**: ID of the PDF to parse
    - **extract_images**: Whether to extract images
    - **extract_tables**: Whether to extract tables
    - Returns parse job status and extracted content
    """
    # Check if PDF exists
    if request.pdf_id not in pdf_storage:
        raise HTTPException(status_code=404, detail="PDF not found")

    pdf_data = pdf_storage[request.pdf_id]

    # Generate parse job ID
    parse_id = f"parse-{uuid.uuid4()}"

    # Mock parsing result (in real implementation, would use PyPDF2/pdfplumber)
    pages = [
        {
            "page": 1,
            "text": "Sample text from page 1",
            "images": [] if not request.extract_images else ["image1.png"],
            "tables": [] if not request.extract_tables else [{"data": "table data"}]
        }
    ]

    metadata = {
        "author": "Unknown",
        "title": pdf_data["filename"],
        "extracted_images": request.extract_images,
        "extracted_tables": request.extract_tables
    }

    return PDFParseResponse(
        id=parse_id,
        pdf_id=request.pdf_id,
        status=ParseStatus.COMPLETED,
        pages=pages,
        metadata=metadata
    )


@router.get("/{pdf_id}/status")
async def get_pdf_status(pdf_id: str):
    """
    Get the status of a PDF processing job

    - **pdf_id**: ID of the PDF
    - Returns current status of the PDF
    """
    if pdf_id not in pdf_storage:
        raise HTTPException(status_code=404, detail="PDF not found")

    pdf_data = pdf_storage[pdf_id]
    response = {
        "id": pdf_id,
        "status": pdf_data["status"]
    }

    # Add task ID if available
    if "task_id" in pdf_data:
        response["task_id"] = pdf_data["task_id"]
        try:
            task_result = AsyncResult(pdf_data["task_id"], app=celery_app)
            response["task_status"] = task_result.state
            response["status"] = _map_task_state(task_result)
            pdf_data["status"] = response["status"]
            if task_result.state == "SUCCESS" and isinstance(task_result.result, dict):
                response["graph_id"] = task_result.result.get("graph_id")
                response["task_info"] = task_result.result
            elif task_result.info:
                response["task_info"] = task_result.info
        except Exception as exc:
            response["task_error"] = str(exc)

    return response


@router.get("/", response_model=List[PDFUploadResponse])
async def list_pdfs():
    """
    List all uploaded PDFs

    - Returns list of all PDFs with their metadata
    """
    return [
        PDFUploadResponse(**pdf_data)
        for pdf_data in pdf_storage.values()
    ]


@router.delete("/{pdf_id}")
async def delete_pdf(pdf_id: str):
    """
    Delete a PDF and its parsed data

    - **pdf_id**: ID of the PDF to delete
    - Returns success message
    """
    if pdf_id not in pdf_storage:
        raise HTTPException(status_code=404, detail="PDF not found")

    # Delete file
    pdf_data = pdf_storage[pdf_id]
    file_path = Path(pdf_data["file_path"])
    if file_path.exists():
        file_path.unlink()

    # Remove from storage
    del pdf_storage[pdf_id]

    return {"message": "PDF deleted successfully"}
