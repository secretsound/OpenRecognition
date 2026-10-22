"""SSE event stream for the console."""

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from openrecognition.api.deps import require_scope

router = APIRouter(prefix="/v1", tags=["events"])

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def _try_put(q: asyncio.Queue, data: dict[str, Any]) -> None:
    try:
        q.put_nowait(data)
    except asyncio.QueueFull:
        _subscribers.discard(q)


def publish_event(data: dict[str, Any]) -> None:
    """Fan out to every connected listener. Drops a full subscriber rather than blocking."""
    loop: asyncio.AbstractEventLoop | None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    for q in list(_subscribers):
        if loop is not None:
            loop.call_soon_threadsafe(_try_put, q, data)
        else:
            _try_put(q, data)


@router.get("/events/stream")
async def event_stream(
    _auth=Depends(require_scope("read")),
):
    q = subscribe()

    async def gen() -> AsyncGenerator[str, None]:
        try:
            yield ": connected\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(item, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
