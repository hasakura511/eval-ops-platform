import json
import os
from pathlib import Path

import pytest

from tools import atp


@pytest.fixture()
def atp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ATP_ROOT", str(tmp_path))
    return tmp_path


def test_sequence_allocation(atp_root):
    info = atp.write_packet("PLAN", "seq-test", None, atp_root)
    assert info.seq == 1
    assert info.path.name == "000001.request.atp"

    info_two = atp.write_packet("PLAN", "seq-test", info.stream_id, atp_root)
    assert info_two.seq == 2
    assert info_two.path.name == "000002.request.atp"


def test_etag_stability(tmp_path):
    packet = tmp_path / "packet.atp"
    packet.write_text(
        "ATP/0.1\n"
        "ID: stream-1/000001\n"
        "TS: 2026-01-19T12:34:56+09:00\n"
        "MODE: PLAN\n"
        "TASK: test\n"
        "STATE: git=abc dirty=0\n"
        "PARENT: none\n"
        "ETAG: <fill_after>\n"
        "TOOLS: read|diff\n"
        "APPROVAL: none\n"
        "\n"
        "GOAL: stable hash\n"
    )
    first = atp.update_etag(packet)
    second = atp.update_etag(packet)
    assert first == second
    assert f"ETAG: {first}" in packet.read_text()


def test_event_append(atp_root):
    info = atp.write_packet("PLAN", "event-test", None, atp_root)
    event_path = atp.append_event(info.stream_id, "PLAN_CREATED", "created", {}, atp_root)
    line = event_path.read_text().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["id"] == f"{info.stream_id}/000001"
    assert payload["type"] == "PLAN_CREATED"
    assert payload["summary"] == "created"
    assert "ts" in payload


def test_bundle_artifact(atp_root):
    input_file = atp_root / "sample.diff"
    input_file.write_text("diff --git a b\n")
    pointer = atp.bundle_artifact("stream-test", "diff", input_file, atp_root)
    pointer_path = Path(pointer)
    assert pointer_path.exists()
    manifest = pointer_path.parent / "manifest.json"
    data = json.loads(manifest.read_text())
    assert data["kind"] == "diff"
    assert input_file.name in data["files"]


def test_schema_validation_sample_packets():
    repo_root = Path(__file__).resolve().parents[1]
    sample_stream = repo_root / "state" / "atp" / "streams" / "sample"
    packet_files = sorted(sample_stream.glob("*.atp"))
    assert packet_files, "Sample packets missing."
    for packet in packet_files:
        parsed = atp.parse_packet_file(packet)
        assert parsed["ATP"] == "ATP/0.1"


def test_approve_appends_review_packet(atp_root):
    info = atp.write_packet("EXEC", "approve-test", None, atp_root)
    stream_path = atp.streams_dir(atp_root) / info.stream_id
    before_packets = sorted(stream_path.glob("*.atp"))

    review = atp.approve_stream(info.stream_id, "approved for release", atp_root)
    after_packets = sorted(stream_path.glob("*.atp"))

    assert review.path.name.endswith(".review.atp")
    assert len(after_packets) == len(before_packets) + 1

    events_path = stream_path / "events.jsonl"
    lines = events_path.read_text().splitlines()
    assert any("APPROVAL_GRANTED" in line for line in lines)
