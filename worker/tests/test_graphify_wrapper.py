"""
Tests for Graphify wrapper
"""
import pytest
from unittest.mock import Mock, patch
from worker.graphify_wrapper import GraphifyProcessor, extract_entities_from_text


class TestGraphifyProcessor:
    """Test GraphifyProcessor initialization and basic operations"""

    def test_processor_init(self):
        """Test GraphifyProcessor initialization"""
        with patch('worker.graphify_wrapper.GraphDatabase.driver'):
            processor = GraphifyProcessor(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password"
            )
            assert processor is not None
            assert processor.neo4j_uri == "bolt://localhost:7687"

    def test_processor_init_with_defaults(self):
        """Test GraphifyProcessor initialization with default values"""
        with patch('worker.graphify_wrapper.GraphDatabase.driver'):
            processor = GraphifyProcessor()
            assert processor is not None
            assert processor.neo4j_user == "neo4j"
            assert processor.neo4j_password == "password"


class TestEntityExtraction:
    """Test entity extraction from text"""

    def test_extract_concepts_basic(self):
        """Test basic concept extraction"""
        text = "二阶系统是控制理论中的重要概念。传递函数描述系统特性。"
        entities = extract_entities_from_text(text)

        assert "concepts" in entities
        assert isinstance(entities["concepts"], list)
        assert len(entities["concepts"]) > 0

    def test_extract_formulas(self):
        """Test formula extraction"""
        text = "二阶系统传递函数为 G(s) = ωn²/(s² + 2ζωns + ωn²)"
        entities = extract_entities_from_text(text)

        assert "formulas" in entities
        assert isinstance(entities["formulas"], list)

    def test_extract_relations(self):
        """Test relationship extraction"""
        text = "二阶系统依赖于阻尼比ζ和自然频率ωn。"
        entities = extract_entities_from_text(text)

        assert "relations" in entities
        assert isinstance(entities["relations"], list)


class TestPDFProcessing:
    """Test PDF processing workflow"""

    @pytest.fixture
    def mock_processor(self):
        """Create a mock processor for testing"""
        with patch('worker.graphify_wrapper.GraphDatabase.driver') as mock_driver:
            processor = GraphifyProcessor(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password"
            )
            # Mock session
            mock_session = Mock()
            mock_driver.return_value.session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_driver.return_value.session.return_value.__exit__ = Mock(return_value=False)
            processor.driver = mock_driver
            return processor

    def test_process_pdf_structure(self, mock_processor):
        """Test that process_pdf returns correct structure"""
        result = mock_processor.process_pdf(
            pdf_path="/fake/path/test.pdf",
            pdf_id="test-pdf-123"
        )

        assert "nodes" in result
        assert "edges" in result
        assert "metadata" in result
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)

    def test_save_to_neo4j_structure(self, mock_processor):
        """Test that Neo4j save operation has correct structure"""
        result = {
            "nodes": [
                {"id": "c1", "name": "二阶系统", "type": "concept", "description": "测试描述"}
            ],
            "edges": [
                {"source": "c1", "target": "c2", "type": "RELATED_TO"}
            ]
        }

        # This should not raise an error
        mock_processor._save_to_neo4j(
            session=mock_processor.driver.session(),
            result=result,
            pdf_id="test-pdf-123"
        )
