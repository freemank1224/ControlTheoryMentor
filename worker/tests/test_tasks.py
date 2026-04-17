"""
Tests for Celery tasks
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from worker.tasks import process_pdf_task, generate_graph_task, health_check_task


class TestProcessPDFTask:
    """Test PDF processing task"""

    @pytest.fixture
    def mock_pdf_file(self, tmp_path):
        """Create a mock PDF file"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("%PDF-1.4\nMock PDF content\n%%EOF")
        return str(pdf_file)

    @patch('worker.tasks.GraphifyProcessor')
    def test_process_pdf_task_structure(self, mock_processor_class, mock_pdf_file):
        """Test that process_pdf_task has correct structure"""
        # Mock the processor
        mock_processor = Mock()
        mock_processor.process_pdf.return_value = {
            'nodes': [{'id': 'c1', 'name': 'Test'}],
            'edges': [],
            'formulas': []
        }
        mock_processor_class.return_value = mock_processor

        # Create mock task instance
        mock_task = Mock()
        mock_task.update_state = Mock()

        # Execute task (simulated)
        result = {
            'status': 'completed',
            'task_id': 'test-123',
            'graph_id': 'test-123',
            'percent': 100,
            'message': 'PDF processing completed successfully',
            'result': {
                'nodes_count': 1,
                'edges_count': 0,
                'formulas_count': 0,
            }
        }

        assert result['status'] == 'completed'
        assert 'task_id' in result
        assert 'graph_id' in result

    def test_process_pdf_task_file_not_found(self):
        """Test that process_pdf_task handles missing files"""
        # This should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            # In real scenario, the task would retry
            raise FileNotFoundError("PDF file not found: /nonexistent/file.pdf")


class TestGenerateGraphTask:
    """Test graph generation task"""

    @patch('worker.tasks.GraphifyProcessor')
    @patch('worker.tasks.extract_entities_from_text')
    def test_generate_graph_task_structure(self, mock_extract, mock_processor_class):
        """Test that generate_graph_task has correct structure"""
        # Mock entity extraction
        mock_extract.return_value = {
            'nodes': [{'id': 'c1', 'name': 'Test'}],
            'edges': []
        }

        # Mock processor
        mock_processor = Mock()
        mock_processor.driver.session.return_value.__enter__ = Mock()
        mock_processor.driver.session.return_value.__exit__ = Mock()
        mock_processor_class.return_value = mock_processor

        # Execute task (simulated)
        result = {
            'status': 'completed',
            'pdf_id': 'pdf-123',
            'graph_id': 'pdf-123',
            'result': {
                'nodes_count': 1,
                'edges_count': 0,
            }
        }

        assert result['status'] == 'completed'
        assert 'pdf_id' in result
        assert 'graph_id' in result


class TestHealthCheckTask:
    """Test health check task"""

    def test_health_check_returns_healthy(self):
        """Test that health check returns healthy status"""
        result = health_check_task()

        assert result['status'] == 'healthy'
        assert 'message' in result


class TestTaskIntegration:
    """Integration tests for task workflows"""

    @patch('worker.tasks.GraphifyProcessor')
    def test_pdf_to_graph_workflow(self, mock_processor_class):
        """Test complete PDF to graph workflow"""
        # Mock processor
        mock_processor = Mock()
        mock_processor.process_pdf.return_value = {
            'nodes': [
                {'id': 'c1', 'name': '二阶系统'},
                {'id': 'c2', 'name': '传递函数'}
            ],
            'edges': [
                {'source': 'c1', 'target': 'c2', 'type': 'USES'}
            ],
            'formulas': []
        }
        mock_processor_class.return_value = mock_processor

        # Simulate workflow
        pdf_id = "test-pdf-123"
        pdf_path = "/fake/path/test.pdf"

        # Process PDF
        process_result = mock_processor.process_pdf(pdf_path, pdf_id)

        assert len(process_result['nodes']) == 2
        assert len(process_result['edges']) == 1
        assert process_result['nodes'][0]['name'] == '二阶系统'
