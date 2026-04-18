from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import pdf, graph, tutor
from app.api.websocket.handler import websocket_endpoint

app = FastAPI(
    title="AI 导师系统 API",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境）
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routes
app.include_router(pdf.router, prefix=settings.API_PREFIX)
app.include_router(graph.router, prefix=settings.API_PREFIX)
app.include_router(tutor.router, prefix=settings.API_PREFIX)

# WebSocket endpoint for real-time task updates
@app.websocket("/ws/graph/{task_id}")
async def websocket_graph_updates(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time PDF processing updates

    Args:
        websocket: WebSocket connection instance
        task_id: Task identifier to monitor
    """
    await websocket_endpoint(websocket, task_id)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
