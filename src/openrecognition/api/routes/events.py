"""SSE event stream."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from openrecognition.api.deps import get_state, require_scope
from openrecognition.app_state import AppState

router = APIRouter(prefix="/v1", tags=["events"])

# Simple in-memory broadcast for SSE demos
_event_queue: asyncio.Queue | None = None


def get_queue() -> asyncio.Queue:
    global _event_queue
    if _event_queue is None:
        _event_queue = asyncio.Queue(maxsize=100)
    return _event_queue


async def publish_event(data: dict) -> None:
    q = get_queue()
    try:
        q.put_nowait(data)
    except asyncio.QueueFull:
        pass


@router.get("/events/stream")
async def event_stream(
    _auth=Depends(require_scope("read")),
):
    async def gen() -> AsyncGenerator[str, None]:
        q = get_queue()
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
