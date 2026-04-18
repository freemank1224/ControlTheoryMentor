"""WebSocket handler for real-time Celery task updates."""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import logging
from celery.result import AsyncResult

from app.celery_client import get_celery_app

logger = logging.getLogger(__name__)
celery_app = get_celery_app()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    """

    def __init__(self):
        # Store active connections by task_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """
        Accept a new WebSocket connection for a specific task

        Args:
            websocket: WebSocket connection instance
            task_id: Task identifier to monitor
        """
        await websocket.accept()

        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()

        self.active_connections[task_id].add(websocket)
        logger.info(f"WebSocket connected for task {task_id}")

        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection.established",
            "data": {
                "task_id": task_id,
                "message": "Connected to task status updates"
            }
        })

    def disconnect(self, websocket: WebSocket, task_id: str):
        """
        Remove a WebSocket connection

        Args:
            websocket: WebSocket connection instance
            task_id: Task identifier
        """
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)

            # Clean up empty sets
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

        logger.info(f"WebSocket disconnected for task {task_id}")

    async def send_update(self, task_id: str, message: dict):
        """
        Send an update to all connected clients for a specific task

        Args:
            task_id: Task identifier
            message: Message payload to send
        """
        if task_id in self.active_connections:
            # Create a copy of the set to avoid modification during iteration
            connections = list(self.active_connections[task_id])

            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to WebSocket: {e}")
                    # Remove problematic connection
                    self.disconnect(connection, task_id)

    async def broadcast(self, task_id: str, message_type: str, data: dict):
        """
        Broadcast a message to all connected clients for a task

        Args:
            task_id: Task identifier
            message_type: Type of message (e.g., "task.progress", "task.completed")
            data: Data payload
        """
        message = {
            "type": message_type,
            "data": data
        }
        await self.send_update(task_id, message)

    async def monitor_task_status(self, task_id: str):
        """
        Monitor a Celery task and stream real progress updates.

        Args:
            task_id: Task identifier to monitor
        """
        try:
            logger.info(f"Starting task monitoring for {task_id}")
            task_result = AsyncResult(task_id, app=celery_app)
            last_snapshot = None

            while True:
                state = task_result.state
                payload = None

                if state == "PENDING":
                    payload = {
                        "type": "task.progress",
                        "data": {
                            "taskId": task_id,
                            "percent": 0,
                            "message": "任务已入队，等待 Worker 处理...",
                        },
                    }
                elif state in {"STARTED", "PROGRESS", "RETRY"}:
                    info = task_result.info if isinstance(task_result.info, dict) else {}
                    payload = {
                        "type": "task.progress",
                        "data": {
                            "taskId": task_id,
                            "percent": int(info.get("percent", 5 if state == "STARTED" else 0)),
                            "message": info.get("message", "Graphify 正在处理文档..."),
                            "status": info.get("status", state.lower()),
                        },
                    }
                elif state == "SUCCESS":
                    result = task_result.result if isinstance(task_result.result, dict) else {}
                    await self.broadcast(
                        task_id,
                        "task.completed",
                        {
                            "taskId": task_id,
                            "graphId": result.get("graph_id", task_id),
                            "message": result.get("message", "Graphify 处理完成"),
                            "result": result.get("result", {}),
                        },
                    )
                    logger.info(f"Task monitoring completed for {task_id}")
                    return
                elif state == "FAILURE":
                    await self.broadcast(
                        task_id,
                        "task.failed",
                        {
                            "taskId": task_id,
                            "error": str(task_result.result),
                        },
                    )
                    return

                if payload and payload != last_snapshot:
                    await self.send_update(task_id, payload)
                    last_snapshot = payload

                await asyncio.sleep(1)
                task_result = AsyncResult(task_id, app=celery_app)

        except Exception as e:
            logger.error(f"Error in monitor_task_status for {task_id}: {e}")
            await self.broadcast(
                task_id,
                "task.failed",
                {
                    "taskId": task_id,
                    "error": str(e),
                },
            )


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for task status updates

    Args:
        websocket: WebSocket connection instance
        task_id: Task identifier to monitor
    """
    await manager.connect(websocket, task_id)

    try:
        # Start monitoring task status
        await manager.monitor_task_status(task_id)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint for task {task_id}: {e}")
    finally:
        manager.disconnect(websocket, task_id)
