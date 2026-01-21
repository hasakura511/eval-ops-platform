import json
import os
from datetime import datetime, timezone
from typing import Iterable, List

import yaml


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_num, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                rows.append(json.loads(raw_line))
            except json.JSONDecodeError as exc:
                snippet = raw_line.strip()
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                raise ValueError(f"Invalid JSON in {path}:{line_num}: {snippet}") from exc
    return rows


def write_jsonl(path: str, rows: Iterable[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def safe_filename(value: str) -> str:
    cleaned = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            cleaned.append(ch)
        else:
            cleaned.append("_")
    return "".join(cleaned)
