from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = REPO_ROOT / "state" / "control_room_latest.json"
HEARTBEAT_INTERVAL_S = 15
POLL_INTERVAL_S = 1


def read_snapshot_bytes() -> bytes:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found: {SNAPSHOT_PATH}")
    return SNAPSHOT_PATH.read_bytes()


def snapshot_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@router.get("/snapshot")
async def get_snapshot() -> JSONResponse:
    try:
        payload = read_snapshot_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=json.loads(payload))


async def event_stream(request: Request) -> AsyncGenerator[str, None]:
    last_hash: str | None = None
    last_error: str | None = None
    last_ping = time.monotonic()

    while True:
        if await request.is_disconnected():
            break

        try:
            payload = read_snapshot_bytes()
            last_error = None
            current_hash = snapshot_hash(payload)
            if current_hash != last_hash:
                last_hash = current_hash
                data = payload.decode("utf-8")
                yield f"event: snapshot\ndata: {data}\n\n"
        except FileNotFoundError as exc:
            message = str(exc)
            if message != last_error:
                last_error = message
                yield f"event: error\ndata: {json.dumps({'message': message})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive logging
            message = str(exc)
            if message != last_error:
                last_error = message
                yield f"event: error\ndata: {json.dumps({'message': message})}\n\n"

        now = time.monotonic()
        if now - last_ping >= HEARTBEAT_INTERVAL_S:
            last_ping = now
            yield "event: ping\ndata: {}\n\n"

        await asyncio.sleep(POLL_INTERVAL_S)


@router.get("/stream")
async def stream_snapshot(request: Request) -> StreamingResponse:
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers=headers,
    )
