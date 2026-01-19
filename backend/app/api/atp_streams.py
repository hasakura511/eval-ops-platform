from __future__ import annotations

import json
import os
import sys
from urllib.parse import unquote
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tools import atp  # noqa: E402

router = APIRouter()


def get_repo_root() -> Path:
    override = os.environ.get("ATP_ROOT")
    if override:
        return Path(override).resolve()
    return REPO_ROOT


def contains_traversal(value: str) -> bool:
    for raw in (value, unquote(value)):
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/"):
            return True
        segments = [segment for segment in normalized.split("/") if segment]
        if any(segment == ".." for segment in segments):
            return True
    return False


def safe_resolve(base: Path, *parts: str) -> Path:
    for part in parts:
        if contains_traversal(part):
            raise HTTPException(status_code=400, detail="Invalid path")
    candidate = (base.joinpath(*parts)).resolve()
    if base == candidate:
        return candidate
    if base not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return candidate


def read_json(path: Path) -> JSONResponse:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return JSONResponse(content=json.loads(path.read_text()))


@router.get("/atp/streams")
def list_streams() -> JSONResponse:
    root = get_repo_root()
    index_file = atp.index_path(root)
    return read_json(index_file)


@router.get("/atp/streams/{stream_id}/packets/{filename}")
def get_packet_file(stream_id: str, filename: str) -> FileResponse:
    root = get_repo_root()
    base = atp.streams_dir(root) / stream_id
    if not base.exists():
        raise HTTPException(status_code=404, detail="Stream not found")
    path = safe_resolve(base, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Packet not found")
    return FileResponse(path)


@router.get("/artifacts/{hash_value}/manifest")
def get_artifact_manifest(hash_value: str) -> FileResponse:
    root = get_repo_root()
    base = atp.artifacts_dir(root) / hash_value
    path = safe_resolve(base, "manifest.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return FileResponse(path)


@router.get("/artifacts/{hash_value}/files/{file_path:path}")
def get_artifact_file(hash_value: str, file_path: str) -> FileResponse:
    root = get_repo_root()
    base = atp.artifacts_dir(root) / hash_value
    if not base.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = safe_resolve(base, file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return FileResponse(path)


@router.post("/atp/streams/{stream_id}/approve")
def approve_stream(stream_id: str, payload: dict) -> JSONResponse:
    root = get_repo_root()
    rationale = payload.get("rationale", "") if isinstance(payload, dict) else ""
    info = atp.approve_stream(stream_id, str(rationale), root)
    response = {
        "stream_id": info.stream_id,
        "sequence": info.seq,
        "path": str(info.path),
    }
    return JSONResponse(content=response)
