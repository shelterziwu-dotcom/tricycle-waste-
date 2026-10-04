"""WebSocket push for live updates (job offers, status changes, collector location).

Clients connect to /ws?token=<jwt>. Endpoints are synchronous and run in a worker
thread, so events are handed to the event loop with anyio.from_thread. Pushing is
best-effort: apps should also refresh via the normal GET endpoints.
"""
from collections import defaultdict

from anyio.from_thread import run as run_in_loop
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.connections[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        self.connections[user_id].discard(ws)

    async def send(self, user_id: int, event: dict) -> None:
        for ws in list(self.connections.get(user_id, ())):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(user_id, ws)

    def notify(self, user_id: int | None, event_type: str, **data) -> None:
        if user_id is None or not self.connections.get(user_id):
            return
        try:
            run_in_loop(self.send, user_id, {"type": event_type, **data})
        except RuntimeError:
            pass  # not called from a worker thread (e.g. scripts); clients will poll


manager = ConnectionManager()
