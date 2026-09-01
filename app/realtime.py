"""In-process WebSocket connection management."""

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Track dashboard sockets by organization in one server process."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, org_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket for an organization."""

        await websocket.accept()
        self._connections.setdefault(org_id, set()).add(websocket)

    def disconnect(self, org_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket and discard empty organization entries."""

        connections = self._connections.get(org_id)
        if connections is None:
            return

        connections.discard(websocket)
        if not connections:
            del self._connections[org_id]

    async def broadcast(self, org_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected socket in an organization."""

        connections = self._connections.get(org_id)
        if not connections:
            return

        for websocket in list(connections):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(org_id, websocket)


connection_manager = ConnectionManager()
