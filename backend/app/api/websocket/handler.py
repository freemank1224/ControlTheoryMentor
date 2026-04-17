"""
WebSocket handler for real-time task status updates
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging
from redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    """

    def __init__(self):
        # Store active connections by task_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_client = None

        try:
            self.redis_client = Redis.from_url(settings.REDIS_URL)
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

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
        Monitor task status and push updates via Redis

        Args:
            task_id: Task identifier to monitor
        """
        if not self.redis_client:
            logger.warning("Redis not available - cannot monitor task status")
            return

        last_status = None

        while task_id in self.active_connections:
            try:
                # Check task status in Redis
                status_key = f"celery-task-meta-{task_id}"
                task_data = self.redis_client.get(status_key)

                if task_data:
                    try:
                        task_info = json.loads(task_data)
                        current_status = task_info.get("status")

                        # Send update if status changed
                        if current_status != last_status:
                            if current_status == "PROGRESS":
                                await self.broadcast(
                                    task_id,
                                    "task.progress",
                                    {
                                        "percent": task_info.get("result", {}).get("percent", 0),
                                        "message": task_info.get("result", {}).get("message", ""),
                                        "task_id": task_id
                                    }
                                )
                            elif current_status == "SUCCESS":
                                await self.broadcast(
                                    task_id,
                                    "task.completed",
                                    {
                                        "task_id": task_id,
                                        "graph_id": task_info.get("result", {}).get("graph_id", task_id)
                                    }
                                )
                                break  # Exit loop on completion
                            elif current_status == "FAILURE":
                                await self.broadcast(
                                    task_id,
                                    "task.failed",
                                    {
                                        "task_id": task_id,
                                        "error": str(task_info.get("result", "Unknown error"))
                                    }
                                )
                                break  # Exit loop on failure

                            last_status = current_status

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in task data for {task_id}")

                # Wait before next check
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error monitoring task {task_id}: {e}")
                await asyncio.sleep(2)  # Wait before retry


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
