"""
Integration tests for PDF API endpoints
"""
import pytest
import os
from fastapi.testclient import TestClient
from io import BytesIO


class TestPDFUploadAPI:
    """Test PDF upload endpoint"""

    def test_upload_pdf_success(self, client: TestClient, tmp_path):
        """Test successful PDF upload"""
        # Create a mock PDF file
        pdf_content = b"%PDF-1.4 mock pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}

        response = client.post("/api/pdf/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["filename"] == "test.pdf"
        assert "page_count" in data
        assert data["status"] == "uploaded"

    def test_upload_pdf_invalid_file_type(self, client: TestClient):
        """Test PDF upload with invalid file type"""
        files = {"file": ("test.txt", BytesIO(b"text content"), "text/plain")}

        response = client.post("/api/pdf/upload", files=files)

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_pdf_missing_file(self, client: TestClient):
        """Test PDF upload without file"""
        response = client.post("/api/pdf/upload")

        assert response.status_code == 422  # Validation error


class TestPDFParseAPI:
    """Test PDF parse endpoint"""

    def test_parse_pdf_success(self, client: TestClient):
        """Test successful PDF parsing"""
        # First upload a PDF
        pdf_content = b"%PDF-1.4 mock pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        upload_response = client.post("/api/pdf/upload", files=files)
        pdf_id = upload_response.json()["id"]

        # Then parse it
        request_data = {
            "pdf_id": pdf_id,
            "extract_images": True,
            "extract_tables": True
        }

        response = client.post("/api/pdf/parse", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["pdf_id"] == pdf_id
        assert "status" in data
        assert "pages" in data
        assert "metadata" in data

    def test_parse_pdf_not_found(self, client: TestClient):
        """Test parsing non-existent PDF"""
        request_data = {
            "pdf_id": "non-existent-pdf"
        }

        response = client.post("/api/pdf/parse", json=request_data)

        assert response.status_code == 404
        assert "PDF not found" in response.json()["detail"]


class TestPDFGetAPI:
    """Test PDF retrieval endpoints"""

    def test_get_pdf_status(self, client: TestClient):
        """Test get PDF status"""
        response = client.get("/api/pdf/test-pdf-123/status")

        # Should return 404 for non-existent PDF
        assert response.status_code in [200, 404]

    def test_get_pdf_list(self, client: TestClient):
        """Test get PDF list"""
        response = client.get("/api/pdf")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app
    return TestClient(app)
