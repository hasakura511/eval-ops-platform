import json
import os
import sys
from pathlib import Path

import pytest

from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from app.api import atp_streams, control_room_snapshot  # noqa: E402
from tools import atp  # noqa: E402


def setup_state(tmp_path: Path) -> None:
    (tmp_path / "state" / "atp" / "streams").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "atp" / "schema").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "control_room_latest.json").write_text(
        json.dumps({"schema_version": "control-room-snapshot-v0", "streams": []})
    )


def test_snapshot_endpoint_returns_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ATP_ROOT", str(tmp_path))
    setup_state(tmp_path)
    response = control_room_snapshot.get_snapshot()
    payload = json.loads(response.body)
    assert payload["schema_version"] == "control-room-snapshot-v0"


def test_packet_and_artifact_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("ATP_ROOT", str(tmp_path))
    setup_state(tmp_path)

    info = atp.write_packet("PLAN", "api-test", None, tmp_path)
    atp.rebuild_index(tmp_path)
    atp.save_index(tmp_path, atp.rebuild_index(tmp_path))

    artifact_dir = tmp_path / "state" / "artifacts" / "abc123"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({"hash": "abc123"}))
    (artifact_dir / "note.txt").write_text("hello")

    packet_response = atp_streams.get_packet_file(info.stream_id, info.path.name)
    assert "ATP/0.1" in Path(packet_response.path).read_text()

    manifest_response = atp_streams.get_artifact_manifest("abc123")
    assert json.loads(Path(manifest_response.path).read_text())["hash"] == "abc123"

    file_response = atp_streams.get_artifact_file("abc123", "note.txt")
    assert Path(file_response.path).read_text() == "hello"


def test_path_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("ATP_ROOT", str(tmp_path))
    setup_state(tmp_path)

    info = atp.write_packet("PLAN", "api-test", None, tmp_path)
    atp.save_index(tmp_path, atp.rebuild_index(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        atp_streams.get_packet_file(info.stream_id, "../index.json")
    assert exc_info.value.status_code == 400
    with pytest.raises(HTTPException) as exc_info:
        atp_streams.get_packet_file(info.stream_id, "%2e%2e%2findex.json")
    assert exc_info.value.status_code == 400

    artifact_dir = tmp_path / "state" / "artifacts" / "abc123"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({"hash": "abc123"}))

    with pytest.raises(HTTPException) as exc_info:
        atp_streams.get_artifact_file("abc123", "../manifest.json")
    assert exc_info.value.status_code == 400
    with pytest.raises(HTTPException) as exc_info:
        atp_streams.get_artifact_file("abc123", "%2e%2e%2fmanifest.json")
    assert exc_info.value.status_code == 400
