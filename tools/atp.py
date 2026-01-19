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
SECTION_HEADERS = {"NOW", "NEXT", "RISKS", "ACCEPT", "ARTIFACTS", "QUESTIONS"}


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


def packet_schema_path(root: Path) -> Path:
    return atp_dir(root) / "schema" / "atp_packet.schema.json"


def event_schema_path(root: Path) -> Path:
    return atp_dir(root) / "schema" / "atp_event.schema.json"


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


def list_packet_files(stream_path: Path) -> list[str]:
    files = []
    if not stream_path.exists():
        return files
    for entry in stream_path.iterdir():
        if entry.is_file() and STREAM_RE.match(entry.name):
            files.append(entry.name)
    return sorted(files)


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


def packet_tools(mode: str) -> list[str]:
    return {
        "PLAN": ["read", "diff"],
        "EXEC": ["edit", "exec"],
        "REVIEW": ["read"],
    }.get(mode, ["read"])


def packet_approval(mode: str) -> str:
    return "requested" if mode == "EXEC" else "none"


def packet_suffix(mode: str) -> str:
    return {
        "PLAN": "request",
        "EXEC": "response",
        "REVIEW": "review",
    }.get(mode, "request")


def split_packet(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.split("\n\n", 1)
    if len(parts) != 2:
        raise ValueError("Packet must contain a blank line separating headers and body.")
    return parts[0], parts[1]


def normalize_nullable(value: str) -> Optional[str]:
    trimmed = value.strip()
    if trimmed.lower() in {"null", "none", ""}:
        return None
    return trimmed


def parse_tools(value: str) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in re.split(r"[|,]", value) if part.strip()]
    return parts


def parse_packet_text(text: str) -> dict:
    header_text, body_text = split_packet(text)
    header_lines = [line for line in header_text.split("\n") if line.strip()]
    if not header_lines:
        raise ValueError("Packet missing header lines.")
    if header_lines[0].strip() != "ATP/0.1":
        raise ValueError("Packet ATP header must be ATP/0.1.")

    headers: dict[str, object] = {"ATP": "ATP/0.1"}
    for line in header_lines[1:]:
        if ":" not in line:
            raise ValueError(f"Invalid header line: {line}")
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    packet = {
        "ATP": headers["ATP"],
        "ID": str(headers.get("ID", "")),
        "TS": str(headers.get("TS", "")),
        "MODE": str(headers.get("MODE", "")),
        "TASK": str(headers.get("TASK", "")),
        "STATE": str(headers.get("STATE", "")),
        "PARENT": normalize_nullable(str(headers.get("PARENT", ""))),
        "ETAG": normalize_nullable(str(headers.get("ETAG", ""))),
        "TOOLS": parse_tools(str(headers.get("TOOLS", ""))),
        "APPROVAL": str(headers.get("APPROVAL", "")),
        "FAIL_CLASS": str(headers.get("FAIL_CLASS", "")),
        "goal": "",
        "now": [],
        "next": [],
        "risks": [],
        "accept": [],
        "artifacts": {"manifests": []},
        "questions": [],
    }

    sections: dict[str, list[str]] = {name: [] for name in SECTION_HEADERS}
    goal = ""
    confidence: Optional[float] = None
    active_section: Optional[str] = None

    for raw_line in body_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("GOAL:"):
            goal = line.replace("GOAL:", "", 1).strip()
            active_section = None
            continue
        if line.startswith("CONFIDENCE:"):
            confidence_text = line.replace("CONFIDENCE:", "", 1).strip()
            try:
                confidence = float(confidence_text)
            except ValueError:
                raise ValueError("CONFIDENCE must be a number.") from None
            active_section = None
            continue
        if line.endswith(":") and line[:-1] in SECTION_HEADERS:
            active_section = line[:-1]
            continue
        if line.startswith("-") and active_section:
            sections[active_section].append(line[1:].strip())
            continue
        raise ValueError(f"Unrecognized body line: {raw_line}")

    packet["goal"] = goal
    packet["now"] = sections["NOW"]
    packet["next"] = sections["NEXT"]
    packet["risks"] = sections["RISKS"]
    packet["accept"] = sections["ACCEPT"]
    packet["questions"] = sections["QUESTIONS"]

    manifests: list[str] = []
    for entry in sections["ARTIFACTS"]:
        if ":" in entry:
            label, value = entry.split(":", 1)
            label = label.strip().lower()
            if label in {"manifest", "manifests"}:
                manifests.append(value.strip())
            else:
                manifests.append(entry.strip())
        else:
            manifests.append(entry.strip())
    packet["artifacts"] = {"manifests": manifests}

    if confidence is not None:
        packet["confidence"] = confidence

    return packet


def render_section(title: str, items: list[str]) -> list[str]:
    lines = [f"{title}:"]
    for item in items:
        lines.append(f"- {item}")
    return lines


def render_packet(packet: dict) -> str:
    tools = ", ".join(packet["TOOLS"])
    parent = "null" if packet["PARENT"] is None else packet["PARENT"]
    etag = "null" if packet["ETAG"] is None else packet["ETAG"]
    lines = [
        "ATP/0.1",
        f"ID: {packet['ID']}",
        f"TS: {packet['TS']}",
        f"MODE: {packet['MODE']}",
        f"TASK: {packet['TASK']}",
        f"STATE: {packet['STATE']}",
        f"PARENT: {parent}",
        f"ETAG: {etag}",
        f"TOOLS: {tools}",
        f"APPROVAL: {packet['APPROVAL']}",
        f"FAIL_CLASS: {packet['FAIL_CLASS']}",
        "",
        f"GOAL: {packet['goal']}",
        "",
    ]

    lines.extend(render_section("NOW", packet["now"]))
    lines.append("")
    lines.extend(render_section("NEXT", packet["next"]))
    lines.append("")
    lines.extend(render_section("RISKS", packet["risks"]))
    lines.append("")
    lines.extend(render_section("ACCEPT", packet["accept"]))
    lines.append("")
    artifact_lines = [f"manifest: {path}" for path in packet["artifacts"]["manifests"]]
    lines.extend(render_section("ARTIFACTS", artifact_lines))
    lines.append("")
    lines.extend(render_section("QUESTIONS", packet["questions"]))

    if "confidence" in packet:
        lines.append("")
        lines.append(f"CONFIDENCE: {packet['confidence']}")

    lines.append("")
    return "\n".join(lines)


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value


def require_optional_string(value: object, label: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string or null.")
    return value


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")
    for entry in value:
        if not isinstance(entry, str):
            raise ValueError(f"{label} must only contain strings.")
    return value


def validate_packet(packet: dict) -> None:
    require_string(packet.get("ATP"), "ATP")
    if packet["ATP"] != "ATP/0.1":
        raise ValueError("ATP must equal ATP/0.1.")
    require_string(packet.get("ID"), "ID")
    require_string(packet.get("TS"), "TS")
    require_string(packet.get("MODE"), "MODE")
    require_string(packet.get("TASK"), "TASK")
    require_string(packet.get("STATE"), "STATE")
    require_optional_string(packet.get("PARENT"), "PARENT")
    require_optional_string(packet.get("ETAG"), "ETAG")

    tools = packet.get("TOOLS")
    require_string_list(tools, "TOOLS")

    approval = packet.get("APPROVAL")
    if approval not in {"none", "requested", "granted_by_human"}:
        raise ValueError("APPROVAL must be none, requested, or granted_by_human.")

    fail_class = packet.get("FAIL_CLASS")
    if fail_class not in {"NONE", "SPEC", "ENV", "TEST", "LOGIC", "INTEGRATION", "DATA", "TOOLING"}:
        raise ValueError("FAIL_CLASS must be a known enum value.")

    require_string(packet.get("goal"), "goal")
    require_string_list(packet.get("now"), "now")
    require_string_list(packet.get("next"), "next")
    require_string_list(packet.get("risks"), "risks")
    require_string_list(packet.get("accept"), "accept")
    require_string_list(packet.get("questions"), "questions")

    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts must be an object.")
    manifests = artifacts.get("manifests")
    require_string_list(manifests, "artifacts.manifests")

    if "confidence" in packet:
        confidence = packet["confidence"]
        if not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be a number between 0 and 1.")
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1.")


def validate_event(payload: dict) -> None:
    require_string(payload.get("ts"), "ts")
    require_string(payload.get("id"), "id")
    require_string(payload.get("type"), "type")
    require_string(payload.get("summary"), "summary")
    packet_id = payload.get("packet_id")
    if packet_id is not None and not isinstance(packet_id, str):
        raise ValueError("packet_id must be a string when provided.")


def build_packet(mode: str, task: str, seq: int, stream_id: str, root: Path) -> dict:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    parent = None if seq == 1 else f"{stream_id}/{seq - 1:06d}"
    state = get_git_state(root)
    packet = {
        "ATP": "ATP/0.1",
        "ID": f"{stream_id}/{seq:06d}",
        "TS": ts,
        "MODE": mode,
        "TASK": task,
        "STATE": state,
        "PARENT": parent,
        "ETAG": None,
        "TOOLS": packet_tools(mode),
        "APPROVAL": packet_approval(mode),
        "FAIL_CLASS": "NONE",
        "goal": "<fill_in>",
        "now": ["<fact 1>"],
        "next": ["<action 1>"],
        "risks": ["<risk 1>"],
        "accept": ["<acceptance 1>"],
        "artifacts": {"manifests": ["state/artifacts/<hash>/manifest.json"]},
        "questions": ["none"],
    }
    validate_packet(packet)
    return packet


def write_packet(mode: str, task: str, stream_id: Optional[str], root: Path) -> PacketInfo:
    ensure_layout(root)
    stream = stream_id or generate_stream_id()
    stream_path = streams_dir(root) / stream
    stream_path.mkdir(parents=True, exist_ok=True)
    seq = next_sequence(stream_path)
    packet = build_packet(mode, task, seq, stream, root)
    packet_path = stream_path / f"{seq:06d}.{packet_suffix(mode)}.atp"
    packet_path.write_text(render_packet(packet))

    index = rebuild_index(root)
    save_index(root, index)

    return PacketInfo(stream_id=stream, seq=seq, path=packet_path)


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


def latest_packet_file(stream_path: Path) -> Path:
    packets = list_packet_files(stream_path)
    if not packets:
        raise ValueError(f"No packets found in {stream_path}")
    return stream_path / packets[-1]


def append_event(
    stream_id: str,
    event_type: str,
    summary: str,
    extra: dict[str, str],
    root: Path,
    packet_id: Optional[str] = None,
    ts_override: Optional[str] = None,
) -> Path:
    ensure_layout(root)
    stream_path = streams_dir(root) / stream_id
    seq = latest_sequence_for_stream(stream_path)
    event_path = stream_path / "events.jsonl"
    ts = ts_override or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "ts": ts,
        "id": f"{stream_id}/{seq:06d}",
        "type": event_type,
        "summary": summary,
    }
    if packet_id:
        payload["packet_id"] = packet_id
    payload.update(extra)
    validate_event(payload)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return event_path


def rebuild_index(root: Path) -> dict:
    ensure_layout(root)
    streams: dict[str, dict[str, object]] = {}
    for stream_dir in sorted(streams_dir(root).iterdir(), key=lambda p: p.name):
        if not stream_dir.is_dir():
            continue
        packet_files = list_packet_files(stream_dir)
        if not packet_files:
            continue
        seqs = [int(STREAM_RE.match(name).group("seq")) for name in packet_files]
        streams[stream_dir.name] = {
            "latest_seq": max(seqs),
            "packet_files": packet_files,
        }
    return {"atp_version": "0.1", "streams": streams}


def parse_packet_file(packet_path: Path) -> dict:
    content = packet_path.read_text()
    packet = parse_packet_text(content)
    validate_packet(packet)
    return packet


def approve_stream(stream_id: str, rationale: str, root: Path) -> PacketInfo:
    ensure_layout(root)
    stream_path = streams_dir(root) / stream_id
    if not stream_path.exists():
        raise FileNotFoundError(f"Stream not found: {stream_id}")

    latest_path = latest_packet_file(stream_path)
    latest_packet = parse_packet_file(latest_path)

    seq = next_sequence(stream_path)
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    packet = {
        "ATP": "ATP/0.1",
        "ID": f"{stream_id}/{seq:06d}",
        "TS": ts,
        "MODE": "REVIEW",
        "TASK": latest_packet["TASK"],
        "STATE": get_git_state(root),
        "PARENT": latest_packet["ID"],
        "ETAG": None,
        "TOOLS": ["read"],
        "APPROVAL": "granted_by_human",
        "FAIL_CLASS": "NONE",
        "goal": "Human approval recorded.",
        "now": [f"Approved {latest_packet['ID']}"],
        "next": ["Continue execution."],
        "risks": ["Human approval could mask unresolved evidence."],
        "accept": [f"Rationale: {rationale}"] if rationale else ["Rationale: none"],
        "artifacts": {"manifests": latest_packet["artifacts"]["manifests"]},
        "questions": ["none"],
    }
    validate_packet(packet)

    packet_path = stream_path / f"{seq:06d}.review.atp"
    packet_path.write_text(render_packet(packet))

    append_event(
        stream_id,
        "APPROVAL_GRANTED",
        "Human approval granted",
        {},
        root,
        packet_id=packet["ID"],
    )

    index = rebuild_index(root)
    save_index(root, index)

    return PacketInfo(stream_id=stream_id, seq=seq, path=packet_path)


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

    index_parser = subparsers.add_parser("index", help="Rebuild state/atp/index.json")
    index_parser.add_argument("--write", action="store_true", help="Write index.json")

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
    event_parser.add_argument("--packet-id")
    event_parser.add_argument("--kv", nargs="*")

    approve_parser = subparsers.add_parser("approve", help="Append a human REVIEW packet")
    approve_parser.add_argument("--stream", required=True)
    approve_parser.add_argument("--rationale", default="")

    show_parser = subparsers.add_parser("show", help="Show parsed packet as JSON")
    show_parser.add_argument("packet_file")

    bundle_parser = subparsers.add_parser("bundle", help="Bundle artifacts into state/artifacts")
    bundle_parser.add_argument("--stream", required=True)
    bundle_parser.add_argument("--kind", required=True, choices=["diff", "logs", "trace", "note"])
    bundle_parser.add_argument("--in", dest="input_path", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = get_repo_root()

    try:
        if args.command == "index":
            index = rebuild_index(root)
            if args.write:
                save_index(root, index)
            print(json.dumps(index, indent=2))
            return 0
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
            event_path = append_event(
                args.stream,
                args.type,
                args.summary,
                extra,
                root,
                packet_id=args.packet_id,
            )
            print(f"Appended {event_path}")
            return 0
        if args.command == "approve":
            info = approve_stream(args.stream, args.rationale, root)
            print(info.path.read_text())
            print(f"Wrote {info.path}")
            return 0
        if args.command == "show":
            packet = parse_packet_file(Path(args.packet_file))
            output = {"headers": {k: packet[k] for k in [
                "ATP", "ID", "TS", "MODE", "TASK", "STATE", "PARENT", "ETAG", "TOOLS", "APPROVAL", "FAIL_CLASS"
            ]}, "body": {k: packet[k] for k in [
                "goal", "now", "next", "risks", "accept", "artifacts", "questions"
            ]}}
            if "confidence" in packet:
                output["body"]["confidence"] = packet["confidence"]
            print(json.dumps(output, indent=2))
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
