"""
Unit tests for PDF schema
"""
import pytest
from pydantic import ValidationError
from app.schemas.pdf import PDFUploadResponse, PDFParseRequest, PDFParseResponse


class TestPDFUploadResponse:
    """Test PDFUploadResponse schema"""

    def test_pdf_upload_response_success(self):
        """Test successful PDF upload response"""
        response = PDFUploadResponse(
            id="pdf-123",
            filename="control-theory.pdf",
            page_count=42,
            status="uploaded"
        )
        assert response.id == "pdf-123"
        assert response.filename == "control-theory.pdf"
        assert response.page_count == 42
        assert response.status == "uploaded"

    def test_pdf_upload_response_invalid_status(self):
        """Test PDF upload response with invalid status"""
        with pytest.raises(ValidationError):
            PDFUploadResponse(
                id="pdf-123",
                filename="control-theory.pdf",
                page_count=42,
                status="invalid_status"
            )


class TestPDFParseRequest:
    """Test PDFParseRequest schema"""

    def test_pdf_parse_request_default_options(self):
        """Test PDF parse request with default options"""
        request = PDFParseRequest(
            pdf_id="pdf-123"
        )
        assert request.pdf_id == "pdf-123"
        assert request.extract_images is True
        assert request.extract_tables is True

    def test_pdf_parse_request_custom_options(self):
        """Test PDF parse request with custom options"""
        request = PDFParseRequest(
            pdf_id="pdf-123",
            extract_images=False,
            extract_tables=False
        )
        assert request.pdf_id == "pdf-123"
        assert request.extract_images is False
        assert request.extract_tables is False

    def test_pdf_parse_request_missing_pdf_id(self):
        """Test PDF parse request without pdf_id"""
        with pytest.raises(ValidationError):
            PDFParseRequest()


class TestPDFParseResponse:
    """Test PDFParseResponse schema"""

    def test_pdf_parse_response_success(self):
        """Test successful PDF parse response"""
        response = PDFParseResponse(
            id="parse-123",
            pdf_id="pdf-123",
            status="completed",
            pages=[{"page": 1, "text": "Sample text"}],
            metadata={"author": "John Doe"}
        )
        assert response.id == "parse-123"
        assert response.pdf_id == "pdf-123"
        assert response.status == "completed"
        assert len(response.pages) == 1
        assert response.metadata["author"] == "John Doe"

    def test_pdf_parse_response_invalid_status(self):
        """Test PDF parse response with invalid status"""
        with pytest.raises(ValidationError):
            PDFParseResponse(
                id="parse-123",
                pdf_id="pdf-123",
                status="invalid_status",
                pages=[],
                metadata={}
            )
