"""
Schemas module for API models
"""
from app.schemas.pdf import PDFUploadResponse, PDFParseRequest, PDFParseResponse
from app.schemas.graph import (
    GraphNode,
    GraphEdge,
    GraphCreateRequest,
    GraphQueryRequest,
    GraphResponse,
    GraphTraversalRequest,
    NodeType,
    RelationType
)
from app.schemas.tutor import (
    TutorMessage,
    TutorRequest,
    TutorResponse,
    QuizRequest,
    QuizResponse,
    ProblemSolvingRequest,
    ProblemSolvingResponse,
    MessageType,
    TutorMode
)

__all__ = [
    "PDFUploadResponse",
    "PDFParseRequest",
    "PDFParseResponse",
    "GraphNode",
    "GraphEdge",
    "GraphCreateRequest",
    "GraphQueryRequest",
    "GraphResponse",
    "GraphTraversalRequest",
    "NodeType",
    "RelationType",
    "TutorMessage",
    "TutorRequest",
    "TutorResponse",
    "QuizRequest",
    "QuizResponse",
    "ProblemSolvingRequest",
    "ProblemSolvingResponse",
    "MessageType",
    "TutorMode",
]
