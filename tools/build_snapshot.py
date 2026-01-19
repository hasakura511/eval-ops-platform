#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools import atp


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def latest_event_timestamp(events_path: Path) -> Optional[datetime]:
    if not events_path.exists():
        return None
    lines = [line for line in events_path.read_text().splitlines() if line.strip()]
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return parse_timestamp(payload.get("ts"))


def derive_status(packet: dict, root: Path) -> str:
    manifests = packet.get("artifacts", {}).get("manifests", [])
    for manifest in manifests:
        manifest_path = (root / manifest).resolve()
        if not manifest_path.exists():
            return "blocked"
    if packet.get("FAIL_CLASS") and packet.get("FAIL_CLASS") != "NONE":
        return "blocked"
    if packet.get("APPROVAL") == "requested":
        return "pending"
    return "running"


def build_snapshot(root: Path) -> dict:
    index = atp.load_index(root)
    streams_summary = []
    latest_timestamp: Optional[datetime] = None

    for stream_id in sorted(index.get("streams", {}).keys()):
        stream_path = atp.streams_dir(root) / stream_id
        packet_files = index["streams"][stream_id].get("packet_files", [])
        if not packet_files:
            continue
        parsed_packets = []
        for filename in packet_files:
            packet_path = stream_path / filename
            parsed_packets.append(atp.parse_packet_file(packet_path))
        parent_map: dict[str, list[str]] = {}
        for parsed in parsed_packets:
            parent = parsed.get("PARENT")
            if not parent:
                continue
            parent_map.setdefault(parent, []).append(parsed["ID"])

        packet = parsed_packets[-1]
        status = derive_status(packet, root)
        event_ts = latest_event_timestamp(stream_path / "events.jsonl")
        packet_ts = parse_timestamp(packet.get("TS"))
        newest = max([ts for ts in [event_ts, packet_ts] if ts], default=None)
        if newest and (latest_timestamp is None or newest > latest_timestamp):
            latest_timestamp = newest
        fork_children = parent_map.get(packet.get("PARENT") or "", [])
        has_fork = len(fork_children) > 1

        streams_summary.append(
            {
                "id": stream_id,
                "latest_seq": index["streams"][stream_id].get("latest_seq"),
                "last_event_ts": event_ts.isoformat() if event_ts else None,
                "status": status,
                "approval_state": packet.get("APPROVAL"),
                "latest_packet_id": packet.get("ID"),
                "fail_class": packet.get("FAIL_CLASS"),
                "packet_files": packet_files,
                "has_fork": has_fork,
                "fork_children": fork_children,
            }
        )

    as_of = latest_timestamp or datetime(1970, 1, 1, tzinfo=timezone.utc)
    blocked_count = sum(1 for stream in streams_summary if stream["status"] == "blocked")
    health_status = "Warning" if blocked_count else "Nominal"

    return {
        "schema_version": "control-room-snapshot-v0",
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "health": {
            "status": health_status,
            "data_freshness_seconds": 0,
            "active_alerts_count": blocked_count,
        },
        "streams": streams_summary,
        "projects": [],
        "alerts": [],
    }


def snapshot_hash(snapshot: dict) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def append_snapshot_events(root: Path, snapshot: dict, digest: str) -> None:
    ts = snapshot.get("as_of")
    for stream in snapshot.get("streams", []):
        stream_id = stream["id"]
        summary = f"Snapshot built for {stream_id}"
        atp.append_event(
            stream_id,
            "SNAPSHOT_BUILT",
            summary,
            {"snapshot_hash": digest},
            root,
            packet_id=stream.get("latest_packet_id"),
            ts_override=ts,
        )


def write_snapshot(root: Path, output_path: Path) -> dict:
    snapshot = build_snapshot(root)
    digest = snapshot_hash(snapshot)
    output_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    append_snapshot_events(root, snapshot, digest)
    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build control room snapshot from ATP streams")
    parser.add_argument("--root", default=str(atp.get_repo_root()))
    parser.add_argument("--output", default="state/control_room_latest.json")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root)
    output_path = root / args.output
    write_snapshot(root, output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
