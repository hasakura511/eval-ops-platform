import json
from pathlib import Path

from tools import atp
from tools import build_snapshot


def test_snapshot_builder_deterministic(tmp_path):
    root = tmp_path
    stream_dir = root / "state" / "atp" / "streams" / "sample"
    stream_dir.mkdir(parents=True)
    (root / "state" / "artifacts").mkdir(parents=True)

    packet = (
        "ATP/0.1\n"
        "ID: sample/000001\n"
        "TS: 2024-02-01T10:00:00Z\n"
        "MODE: PLAN\n"
        "TASK: snapshot-test\n"
        "STATE: git=unknown dirty=1\n"
        "PARENT: null\n"
        "ETAG: null\n"
        "TOOLS: read\n"
        "APPROVAL: none\n"
        "FAIL_CLASS: NONE\n"
        "\n"
        "GOAL: Snapshot baseline.\n"
        "\n"
        "NOW:\n"
        "- Seed test packets.\n"
        "\n"
        "NEXT:\n"
        "- Build snapshot.\n"
        "\n"
        "RISKS:\n"
        "- None.\n"
        "\n"
        "ACCEPT:\n"
        "- Snapshot is deterministic.\n"
        "\n"
        "ARTIFACTS:\n"
        "- manifest: state/artifacts/missing-hash/manifest.json\n"
        "\n"
        "QUESTIONS:\n"
        "- none\n"
    )
    (stream_dir / "000001.request.atp").write_text(packet)
    (stream_dir / "events.jsonl").write_text(
        '{"ts":"2024-02-01T10:00:05Z","id":"sample/000001","type":"PLAN_CREATED","summary":"created"}\n'
    )

    atp.save_index(root, atp.rebuild_index(root))

    first = build_snapshot.build_snapshot(root)
    second = build_snapshot.build_snapshot(root)

    assert first == second
    assert first["streams"][0]["status"] == "blocked"

    output_path = root / "state" / "control_room_latest.json"
    build_snapshot.write_snapshot(root, output_path)
    written = json.loads(output_path.read_text())
    assert written == first
