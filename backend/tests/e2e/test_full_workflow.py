"""
E2E tests for full system workflow

This test suite requires all services to be running:
- Backend API (http://localhost:8000)
- Neo4j database (bolt://localhost:7687)
- Redis cache (localhost:6379)
- Worker service for background tasks

To run: pytest backend/tests/e2e/test_full_workflow.py

To skip if services are not available: pytest backend/tests/e2e/test_full_workflow.py -m "not e2e"
"""
import pytest
import asyncio
import time
from typing import Generator, Optional
import httpx
from io import BytesIO


# pytest markers
pytestmark = pytest.mark.e2e


class TestFullWorkflow:
    """Test complete user workflows end-to-end"""

    @pytest.fixture(scope="class")
    def api_base_url(self) -> str:
        """Base URL for API tests"""
        return "http://localhost:8000"

    @pytest.fixture(scope="class")
    def client(self) -> Generator[httpx.AsyncClient, None, None]:
        """Create async HTTP client for testing"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client

    @pytest.fixture(autouse=True)
    async def health_check(self, api_base_url: str, client: httpx.AsyncClient):
        """Check if services are running before each test"""
        try:
            response = await client.get(f"{api_base_url}/health")
            if response.status_code != 200:
                pytest.skip("Backend service not healthy")
        except Exception as e:
            pytest.skip(f"Cannot connect to backend service: {e}")

    async def test_pdf_upload_to_graph_workflow(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """
        Test complete workflow:
        1. Upload PDF
        2. Parse PDF
        3. Extract knowledge graph
        4. Query graph
        """
        # Step 1: Upload PDF
        pdf_content = b"%PDF-1.4\n%mock pdf content for testing"
        files = {"file": ("test_control.pdf", BytesIO(pdf_content), "application/pdf")}

        upload_response = await client.post(
            f"{api_base_url}/api/pdf/upload", files=files
        )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        pdf_id = upload_data["id"]
        assert pdf_id is not None
        assert upload_data["status"] in ["uploaded", "processing"]

        # Step 2: Parse PDF
        parse_request = {
            "pdf_id": pdf_id,
            "extract_images": False,
            "extract_tables": False,
        }

        parse_response = await client.post(
            f"{api_base_url}/api/pdf/parse", json=parse_request
        )

        assert parse_response.status_code in [200, 202]  # May be async
        parse_data = parse_response.json()
        task_id = parse_data.get("id")

        # Step 3: Wait for parsing to complete (if async)
        if task_id:
            max_wait = 30
            start_time = time.time()

            while time.time() - start_time < max_wait:
                status_response = await client.get(
                    f"{api_base_url}/api/pdf/{pdf_id}/status"
                )
                status_data = status_response.json()

                if status_data.get("status") == "completed":
                    break

                await asyncio.sleep(2)

        # Step 4: Query knowledge graph
        graph_query = {
            "query": "MATCH (n:Concept) RETURN n LIMIT 10",
            "pdf_id": pdf_id,
        }

        graph_response = await client.post(
            f"{api_base_url}/api/graph/query", json=graph_query
        )

        assert graph_response.status_code == 200
        graph_data = graph_response.json()
        assert "nodes" in graph_data
        assert "edges" in graph_data

    async def test_tutor_interaction_with_context(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """
        Test tutor interaction workflow:
        1. Start conversation
        2. Ask question about control theory
        3. Get follow-up response
        4. Generate quiz
        """
        # Step 1: Initial question
        chat_request = {
            "message": "What is a PID controller in control systems?",
            "mode": "interactive",
        }

        chat_response = await client.post(
            f"{api_base_url}/api/tutor/chat", json=chat_request
        )

        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert "message" in chat_data
        assert "conversation_id" in chat_data
        conversation_id = chat_data["conversation_id"]

        # Step 2: Follow-up question
        followup_request = {
            "message": "Can you explain the P, I, and D terms?",
            "conversation_id": conversation_id,
            "mode": "interactive",
        }

        followup_response = await client.post(
            f"{api_base_url}/api/tutor/chat", json=followup_request
        )

        assert followup_response.status_code == 200
        followup_data = followup_response.json()
        assert "message" in followup_data
        assert followup_data["conversation_id"] == conversation_id

        # Step 3: Generate quiz
        quiz_request = {
            "topic": "PID Controllers",
            "difficulty": "medium",
            "question_count": 3,
        }

        quiz_response = await client.post(
            f"{api_base_url}/api/tutor/quiz", json=quiz_request
        )

        assert quiz_response.status_code == 200
        quiz_data = quiz_response.json()
        assert "quiz_id" in quiz_data
        assert "questions" in quiz_data
        assert len(quiz_data["questions"]) == 3

    async def test_graph_visualization_workflow(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """
        Test knowledge graph visualization workflow:
        1. Create sample knowledge nodes
        2. Query subgraph
        3. Get visualization format
        """
        # Step 1: Add sample node
        node_request = {
            "label": "TransferFunction",
            "properties": {
                "name": "Second Order System",
                "equation": "G(s) = ωn²/(s² + 2ζωns + ωn²)",
                "type": "concept",
            },
        }

        node_response = await client.post(
            f"{api_base_url}/api/graph/nodes", json=node_request
        )

        assert node_response.status_code in [200, 201]
        node_data = node_response.json()
        assert "id" in node_data
        node_id = node_data["id"]

        # Step 2: Add related node
        node2_request = {
            "label": "Parameter",
            "properties": {"name": "Natural Frequency", "symbol": "ωn", "unit": "rad/s"},
        }

        node2_response = await client.post(
            f"{api_base_url}/api/graph/nodes", json=node2_request
        )

        assert node2_response.status_code in [200, 201]
        node2_data = node2_response.json()
        node2_id = node2_data["id"]

        # Step 3: Create relationship
        edge_request = {
            "source_id": node_id,
            "target_id": node2_id,
            "relationship_type": "CONTAINS",
            "properties": {"strength": 0.9},
        }

        edge_response = await client.post(
            f"{api_base_url}/api/graph/edges", json=edge_request
        )

        assert edge_response.status_code in [200, 201]

        # Step 4: Get subgraph for visualization
        subgraph_request = {"node_id": node_id, "depth": 1}

        subgraph_response = await client.post(
            f"{api_base_url}/api/graph/subgraph", json=subgraph_request
        )

        assert subgraph_response.status_code == 200
        subgraph_data = subgraph_response.json()
        assert "nodes" in subgraph_data
        assert "edges" in subgraph_data
        assert len(subgraph_data["nodes"]) >= 1

    async test_problem_solving_workflow(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """
        Test problem-solving workflow:
        1. Submit control theory problem
        2. Get step-by-step solution
        3. Request hints
        """
        problem_request = {
            "problem_statement": "Design a PID controller for a system with transfer function G(s) = 1/(s+1)(s+2)",
            "subject": "control systems",
            "hints_requested": 3,
        }

        response = await client.post(
            f"{api_base_url}/api/tutor/solve", json=problem_request
        )

        assert response.status_code == 200
        data = response.json()
        assert "solution_steps" in data
        assert "hints" in data
        assert "explanation" in data
        assert len(data["hints"]) == 3

    async def test_conversation_persistence(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """
        Test conversation history persistence:
        1. Create conversation
        2. Add multiple messages
        3. Retrieve conversation history
        """
        # Create conversation with first message
        msg1_request = {
            "message": "Explain stability in control systems",
            "mode": "interactive",
        }

        msg1_response = await client.post(
            f"{api_base_url}/api/tutor/chat", json=msg1_request
        )

        assert msg1_response.status_code == 200
        conversation_id = msg1_response.json()["conversation_id"]

        # Add second message
        msg2_request = {
            "message": "What are the stability criteria?",
            "conversation_id": conversation_id,
        }

        msg2_response = await client.post(
            f"{api_base_url}/api/tutor/chat", json=msg2_request
        )

        assert msg2_response.status_code == 200

        # Add third message
        msg3_request = {
            "message": "Give me an example of an unstable system",
            "conversation_id": conversation_id,
        }

        msg3_response = await client.post(
            f"{api_base_url}/api/tutor/chat", json=msg3_request
        )

        assert msg3_response.status_code == 200

        # Retrieve conversation history
        history_response = await client.get(
            f"{api_base_url}/api/tutor/conversations/{conversation_id}"
        )

        assert history_response.status_code == 200
        history_data = history_response.json()
        assert "messages" in history_data
        assert len(history_data["messages"]) >= 3


class TestErrorHandling:
    """Test error handling in E2E scenarios"""

    @pytest.fixture(scope="class")
    def api_base_url(self) -> str:
        return "http://localhost:8000"

    @pytest.fixture(scope="class")
    def client(self) -> Generator[httpx.AsyncClient, None, None]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client

    @pytest.fixture(autouse=True)
    async def health_check(self, api_base_url: str, client: httpx.AsyncClient):
        try:
            response = await client.get(f"{api_base_url}/health")
            if response.status_code != 200:
                pytest.skip("Backend service not healthy")
        except Exception:
            pytest.skip("Cannot connect to backend service")

    async def test_invalid_pdf_upload(self, api_base_url: str, client: httpx.AsyncClient):
        """Test uploading invalid file type"""
        files = {
            "file": ("test.txt", BytesIO(b"This is not a PDF"), "text/plain")
        }

        response = await client.post(f"{api_base_url}/api/pdf/upload", files=files)

        assert response.status_code == 400

    async def test_nonexistent_pdf_parse(self, api_base_url: str, client: httpx.AsyncClient):
        """Test parsing non-existent PDF"""
        request = {"pdf_id": "nonexistent-pdf-id"}

        response = await client.post(f"{api_base_url}/api/pdf/parse", json=request)

        assert response.status_code == 404

    async def test_invalid_graph_query(self, api_base_url: str, client: httpx.AsyncClient):
        """Test invalid graph query"""
        request = {"query": "INVALID CYPHER QUERY"}

        response = await client.post(f"{api_base_url}/api/graph/query", json=request)

        assert response.status_code in [400, 422]

    async def test_nonexistent_conversation(
        self, api_base_url: str, client: httpx.AsyncClient
    ):
        """Test retrieving non-existent conversation"""
        response = await client.get(
            f"{api_base_url}/api/tutor/conversations/nonexistent-id"
        )

        assert response.status_code == 404
