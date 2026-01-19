#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

STREAM_RE = re.compile(r"^(?P<seq>\d{6})\..+\.atp$")
ETAG_RE = re.compile(r"^ETAG:.*$", re.MULTILINE)


@dataclass(frozen=True)
class PacketInfo:
    stream_id: str
    seq: int
    path: Path


def get_repo_root() -> Path:
    override = os.environ.get("ATP_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[1]


def state_dir(root: Path) -> Path:
    return root / "state"


def atp_dir(root: Path) -> Path:
    return state_dir(root) / "atp"


def streams_dir(root: Path) -> Path:
    return atp_dir(root) / "streams"


def artifacts_dir(root: Path) -> Path:
    return state_dir(root) / "artifacts"


def index_path(root: Path) -> Path:
    return atp_dir(root) / "index.json"


def ensure_layout(root: Path) -> None:
    streams_dir(root).mkdir(parents=True, exist_ok=True)
    artifacts_dir(root).mkdir(parents=True, exist_ok=True)
    idx_path = index_path(root)
    if not idx_path.exists():
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(json.dumps({"atp_version": "0.1", "streams": {}}, indent=2) + "\n")


def load_index(root: Path) -> dict:
    idx_path = index_path(root)
    if not idx_path.exists():
        return {"atp_version": "0.1", "streams": {}}
    return json.loads(idx_path.read_text())


def save_index(root: Path, data: dict) -> None:
    index_path(root).write_text(json.dumps(data, indent=2) + "\n")


def list_sequences(stream_path: Path) -> list[int]:
    if not stream_path.exists():
        return []
    seqs = []
    for entry in stream_path.iterdir():
        if not entry.is_file():
            continue
        match = STREAM_RE.match(entry.name)
        if match:
            seqs.append(int(match.group("seq")))
    return sorted(seqs)


def next_sequence(stream_path: Path) -> int:
    seqs = list_sequences(stream_path)
    return (seqs[-1] + 1) if seqs else 1


def generate_stream_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"stream-{timestamp}"


def get_git_state(root: Path) -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        sha_text = sha.decode().strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root).decode().strip()
        dirty_flag = "1" if dirty else "0"
        return f"git={sha_text} dirty={dirty_flag}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "git=unknown dirty=1"


def packet_tools(mode: str) -> str:
    return {
        "PLAN": "read|diff",
        "EXEC": "edit|exec",
        "REVIEW": "read",
    }.get(mode, "read")


def packet_approval(mode: str) -> str:
    return "requested" if mode == "EXEC" else "none"


def packet_status(mode: str) -> str:
    return "NEEDS_INFO" if mode == "PLAN" else "OK"


def format_packet(mode: str, task: str, seq: int, stream_id: str, root: Path) -> str:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    parent = "none" if seq == 1 else "<parent_etag>"
    state = get_git_state(root)
    tools = packet_tools(mode)
    approval = packet_approval(mode)
    status = packet_status(mode)
    return (
        "ATP/0.1\n"
        f"ID: {stream_id}/{seq:06d}\n"
        f"TS: {ts}\n"
        f"MODE: {mode}\n"
        f"TASK: {task}\n"
        f"STATE: {state}\n"
        f"PARENT: {parent}\n"
        "ETAG: <fill_after>\n"
        f"TOOLS: {tools}\n"
        f"APPROVAL: {approval}\n"
        "\n"
        "GOAL: <fill_in>\n"
        "\n"
        "NOW:\n"
        "- <fact 1>\n"
        "\n"
        "NEXT:\n"
        "- <action 1>\n"
        "\n"
        "RISKS:\n"
        "- <risk 1>\n"
        "\n"
        "ACCEPT:\n"
        "- <acceptance 1>\n"
        "\n"
        "ARTIFACTS:\n"
        "- manifest: state/artifacts/<hash>/manifest.json\n"
        "\n"
        "QUESTIONS:\n"
        "- none\n"
        "\n"
        f"STATUS: {status}\n"
        "FAIL_CLASS: NONE\n"
        "FAIL_SYMPTOM: none\n"
    )


def write_packet(mode: str, task: str, stream_id: Optional[str], root: Path) -> PacketInfo:
    ensure_layout(root)
    stream = stream_id or generate_stream_id()
    stream_path = streams_dir(root) / stream
    stream_path.mkdir(parents=True, exist_ok=True)
    seq = next_sequence(stream_path)
    packet_text = format_packet(mode, task, seq, stream, root)
    packet_path = stream_path / f"{seq:06d}.request.atp"
    packet_path.write_text(packet_text)

    index = load_index(root)
    index.setdefault("streams", {})
    index["streams"][stream] = {"latest_seq": seq}
    save_index(root, index)

    return PacketInfo(stream_id=stream, seq=seq, path=packet_path)


def split_packet(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.split("\n\n", 1)
    if len(parts) != 2:
        raise ValueError("Packet must contain a blank line separating headers and body.")
    return parts[0], parts[1]


def update_etag(packet_path: Path) -> str:
    content = packet_path.read_text()
    header, body = split_packet(content)
    payload = body
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    updated_header = ETAG_RE.sub(f"ETAG: {digest}", header)
    if updated_header == header:
        updated_header = header + f"\nETAG: {digest}"
    updated_content = updated_header + "\n\n" + body
    packet_path.write_text(updated_content)
    return digest


def latest_sequence_for_stream(stream_path: Path) -> int:
    seqs = list_sequences(stream_path)
    if not seqs:
        raise ValueError(f"No packets found in {stream_path}")
    return seqs[-1]


def append_event(
    stream_id: str,
    event_type: str,
    summary: str,
    extra: dict[str, str],
    root: Path,
) -> Path:
    ensure_layout(root)
    stream_path = streams_dir(root) / stream_id
    seq = latest_sequence_for_stream(stream_path)
    event_path = stream_path / "events.jsonl"
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "ts": ts,
        "id": f"{stream_id}/{seq:06d}",
        "type": event_type,
        "summary": summary,
    }
    payload.update(extra)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return event_path


def hash_files(paths: Iterable[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        hasher.update(str(path).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def collect_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        files = []
        for root, _, filenames in os.walk(input_path):
            for name in filenames:
                files.append(Path(root) / name)
        return files
    raise FileNotFoundError(f"Input path not found: {input_path}")


def bundle_artifact(stream_id: str, kind: str, input_path: Path, root: Path) -> str:
    ensure_layout(root)
    input_path = input_path.resolve()
    files = collect_paths(input_path)
    digest = hash_files(files)
    destination = artifacts_dir(root) / digest
    destination.mkdir(parents=True, exist_ok=True)

    manifest = {
        "hash": digest,
        "kind": kind,
        "stream": stream_id,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": str(input_path),
        "files": [],
    }

    if input_path.is_file():
        target = destination / input_path.name
        shutil.copy2(input_path, target)
        manifest["files"].append(input_path.name)
    else:
        for file_path in files:
            rel_path = file_path.relative_to(input_path)
            target = destination / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target)
            manifest["files"].append(str(rel_path))

    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if input_path.is_file():
        return str(destination / input_path.name)
    return str(destination / "manifest.json")


def parse_kv_pairs(items: Optional[list[str]]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    if not items:
        return pairs
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid key/value pair: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError(f"Invalid key/value pair: {item}")
        pairs[key] = value
    return pairs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATP helper tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a new ATP packet")
    new_parser.add_argument("--mode", required=True, choices=["PLAN", "EXEC", "REVIEW"])
    new_parser.add_argument("--task", required=True)
    new_parser.add_argument("--stream")

    etag_parser = subparsers.add_parser("etag", help="Compute and set ETAG for packet")
    etag_parser.add_argument("packet_file")

    event_parser = subparsers.add_parser("event", help="Append an event to events.jsonl")
    event_parser.add_argument("--stream", required=True)
    event_parser.add_argument("--type", required=True)
    event_parser.add_argument("--summary", required=True)
    event_parser.add_argument("--kv", nargs="*")

    bundle_parser = subparsers.add_parser("bundle", help="Bundle artifacts into state/artifacts")
    bundle_parser.add_argument("--stream", required=True)
    bundle_parser.add_argument("--kind", required=True, choices=["diff", "logs", "trace"])
    bundle_parser.add_argument("--in", dest="input_path", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = get_repo_root()

    try:
        if args.command == "new":
            info = write_packet(args.mode, args.task, args.stream, root)
            content = info.path.read_text()
            print(content)
            print(f"Wrote {info.path}")
            return 0
        if args.command == "etag":
            packet_path = Path(args.packet_file)
            digest = update_etag(packet_path)
            print(digest)
            return 0
        if args.command == "event":
            extra = parse_kv_pairs(args.kv)
            event_path = append_event(args.stream, args.type, args.summary, extra, root)
            print(f"Appended {event_path}")
            return 0
        if args.command == "bundle":
            pointer = bundle_artifact(args.stream, args.kind, Path(args.input_path), root)
            print(pointer)
            return 0
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
