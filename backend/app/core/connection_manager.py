"""
WebSocket connection manager.

Handles client connections, broadcasting, and session tracking.
"""
import asyncio
from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Manages active WebSocket connections and per-session state."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._session_tasks: dict[str, set[asyncio.Task]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await websocket.accept()
        self._connections[session_id] = websocket
        self._session_tasks[session_id] = set()
        logger.info(f"Session [{session_id}] connected ({len(self._connections)} active)")

    def disconnect(self, session_id: str) -> None:
        """Remove a connection and cancel its tasks."""
        if session_id in self._session_tasks:
            for task in self._session_tasks[session_id]:
                task.cancel()
            del self._session_tasks[session_id]

        if session_id in self._connections:
            del self._connections[session_id]
            logger.info(f"Session [{session_id}] disconnected ({len(self._connections)} active)")

    async def send_json(self, session_id: str, data: dict) -> None:
        """Send a JSON message to a specific session."""
        ws = self._connections.get(session_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to [{session_id}]: {e}")
                self.disconnect(session_id)

    async def broadcast(self, data: dict) -> None:
        """Send a JSON message to all connected sessions."""
        disconnected = []
        for sid, ws in self._connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(sid)
        for sid in disconnected:
            self.disconnect(sid)

    def register_task(self, session_id: str, task: asyncio.Task) -> None:
        """Register a background task for a session."""
        if session_id in self._session_tasks:
            self._session_tasks[session_id].add(task)
            task.add_done_callback(lambda t: self._session_tasks[session_id].discard(t))

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Singleton instance
manager = ConnectionManager()
