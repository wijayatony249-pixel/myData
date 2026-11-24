"""
Manajer Server-Sent Events (SSE) untuk Streaming Status Klaster Real-Time ke Dashboard Web.
"""

import asyncio
import json
from typing import Set
from fastapi import Request

class SSEManager:
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        """Mendaftarkan klien baru untuk menerima stream event."""
        q = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Menghapus pendaftaran klien."""
        self._subscribers.discard(q)

    async def broadcast(self, event_type: str, data: dict):
        """Mengirimkan pesan event ke seluruh klien web yang terhubung."""
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                self.unsubscribe(q)
            except Exception:
                pass

sse_manager = SSEManager()
