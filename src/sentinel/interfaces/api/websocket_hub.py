"""WebSocket hub for real-time live incident, health, and stats streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("sentinel.interfaces.api.websocket_hub")


class WebSocketHub:
    """Manages active WebSocket connections with heartbeats and slow-client drop policy."""

    def __init__(self, max_queue_size: int = 100) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.max_queue_size = max_queue_size
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.debug("WebSocket client connected. Total clients: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.debug(
            "WebSocket client disconnected. Total clients: %d", len(self.active_connections)
        )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcasts a JSON message to all active clients, dropping slow or disconnected ones."""
        payload = json.dumps(message)
        async with self._lock:
            clients = list(self.active_connections)

        dead_clients: Set[WebSocket] = set()
        for ws in clients:
            try:
                await asyncio.wait_for(ws.send_text(payload), timeout=0.5)
            except Exception:
                dead_clients.add(ws)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    self.active_connections.discard(ws)
