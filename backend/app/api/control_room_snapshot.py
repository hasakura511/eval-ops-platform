from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = REPO_ROOT / "state" / "control_room_latest.json"


def snapshot_path() -> Path:
    override = os.environ.get("ATP_ROOT")
    if override:
        return Path(override).resolve() / "state" / "control_room_latest.json"
    return SNAPSHOT_PATH


@router.get("/control-room/snapshot")
def get_snapshot() -> JSONResponse:
    path = snapshot_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {path}")
    return JSONResponse(content=json.loads(path.read_text()))
