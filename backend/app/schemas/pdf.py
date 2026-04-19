"""
PDF schemas for request and response models
"""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class PDFStatus(str, Enum):
    """PDF status enumeration"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ParseStatus(str, Enum):
    """Parse status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PDFUploadResponse(BaseModel):
    """Response model for PDF upload"""
    id: str = Field(..., description="Unique PDF identifier")
    taskId: Optional[str] = Field(default=None, description="Task identifier for WebSocket tracking")
    filename: str = Field(..., description="Original filename")
    page_count: int = Field(..., ge=1, description="Number of pages in PDF")
    status: PDFStatus = Field(..., description="Upload status")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "pdf-123",
                "taskId": "task-123",
                "filename": "control-theory.pdf",
                "page_count": 42,
                "status": "uploaded"
            }
        }


class PDFParseRequest(BaseModel):
    """Request model for PDF parsing"""
    pdf_id: str = Field(..., description="PDF identifier to parse")
    extract_images: bool = Field(default=True, description="Extract images from PDF")
    extract_tables: bool = Field(default=True, description="Extract tables from PDF")

    class Config:
        json_schema_extra = {
            "example": {
                "pdf_id": "pdf-123",
                "extract_images": True,
                "extract_tables": True
            }
        }


class PDFParseResponse(BaseModel):
    """Response model for PDF parsing"""
    id: str = Field(..., description="Parse job identifier")
    pdf_id: str = Field(..., description="Original PDF identifier")
    status: ParseStatus = Field(..., description="Parse status")
    pages: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted pages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="PDF metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "parse-123",
                "pdf_id": "pdf-123",
                "status": "completed",
                "pages": [
                    {
                        "page": 1,
                        "text": "Sample text"
                    }
                ],
                "metadata": {
                    "author": "John Doe",
                    "title": "Control Theory"
                }
            }
        }
