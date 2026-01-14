#!/usr/bin/env python3
"""Contract tests for Bureaucratic Autoregression telemetry and dashboard mapping."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ARTIFACT_PATTERN = re.compile(r"^artifact:[A-Za-z0-9._@:-]+$")
HASH_PATTERN = re.compile(r"^hash:[A-Za-z0-9]+$")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _find_states(state_dir: Path) -> list[Path]:
    history_dir = state_dir / "history"
    history_files = sorted(history_dir.glob("t=*.json"))
    latest = state_dir / "latest.json"
    if not latest.exists():
        raise FileNotFoundError("state/latest.json not found")
    return [latest, *history_files]


def _collect_artifact_refs(payload: Any) -> Iterable[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("_ref") and isinstance(value, str):
                if ARTIFACT_PATTERN.match(value):
                    yield value
            if key in {
                "recent_artifacts",
                "recent_decisions",
                "recent_audits",
                "variance_memos",
                "evidence_refs",
            }:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and ARTIFACT_PATTERN.match(item):
                            yield item
            yield from _collect_artifact_refs(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _collect_artifact_refs(item)


def _require_path(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    cursor: Any = data
    for key in path.split("."):
        if not isinstance(cursor, dict) or key not in cursor:
            return False, None
        cursor = cursor[key]
    return True, cursor


def _validate_page_requirements(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    errors: list[str] = []

    required_paths = [
        "physics.admin_ratio",
        "B_t.Pi_t.beta",
        "physics.rule_entropy",
        "evaluation.Risk(x_t)",
    ]
    recommended_paths = ["B_t.Pi_t.r"]

    for path in required_paths:
        present, _ = _require_path(payload, path)
        if not present:
            errors.append(f"Missing executive field: {path}")

    for path in recommended_paths:
        present, _ = _require_path(payload, path)
        if not present:
            warnings.append(f"Recommended executive field missing: {path}")

    inspectorate_paths = [
        "physics.goodhart",
        "evaluation.audit",
        "alerts",
    ]
    for path in inspectorate_paths:
        present, _ = _require_path(payload, path)
        if not present:
            errors.append(f"Missing inspectorate field: {path}")

    records_paths = [
        "B_t.L_t.ledger_head",
        "B_t.L_t.provenance_ref",
    ]
    for path in records_paths:
        present, _ = _require_path(payload, path)
        if not present:
            errors.append(f"Missing records field: {path}")

    operations_paths = [
        "B_t.A_t.units",
    ]
    for path in operations_paths:
        present, value = _require_path(payload, path)
        if not present or not isinstance(value, list) or not value:
            errors.append("Missing operations units list")
        elif isinstance(value, list):
            for idx, unit in enumerate(value):
                if "D_i" not in unit:
                    errors.append(f"Missing D_i for unit index {idx}")
                if "variance_memos" not in unit:
                    errors.append(f"Missing variance_memos for unit index {idx}")

    if errors:
        raise AssertionError("; ".join(errors))

    return warnings


def _validate_artifact_refs(payload: dict[str, Any], records_dir: Path) -> None:
    missing: list[str] = []
    artifacts_dir = records_dir / "artifacts"

    for ref in sorted(set(_collect_artifact_refs(payload))):
        artifact_id = ref.split("artifact:", 1)[1]
        target = artifacts_dir / f"{artifact_id}.json"
        if not target.exists():
            missing.append(ref)

    if missing:
        raise AssertionError(f"Missing artifact records for: {', '.join(missing)}")

    provenance_ref = payload["B_t"]["L_t"]["provenance_ref"]
    if not ARTIFACT_PATTERN.match(provenance_ref):
        raise AssertionError("Invalid provenance_ref format")
    provenance_id = provenance_ref.split("artifact:", 1)[1]
    provenance_path = records_dir / "provenance" / f"{provenance_id}.json"
    if not provenance_path.exists():
        raise AssertionError(f"Missing provenance file: {provenance_path}")
    provenance_payload = _load_json(provenance_path)
    if "nodes" not in provenance_payload or "edges" not in provenance_payload:
        raise AssertionError("Provenance file missing nodes/edges")


def _validate_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: err.path)
    if errors:
        formatted = "\n".join(
            f"{'.'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise AssertionError(f"Schema validation failed:\n{formatted}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Contract tests for telemetry snapshots.")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("state"),
        help="Directory containing latest.json and history/.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/state.schema.json"),
        help="Path to JSON Schema for state.json.",
    )
    parser.add_argument(
        "--records-dir",
        type=Path,
        default=Path("records"),
        help="Directory containing records artifacts/provenance.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    schema = _load_json(args.schema)

    warnings: list[str] = []
    for path in _find_states(args.state_dir):
        payload = _load_json(path)
        _validate_schema(payload, schema)
        warnings.extend(_validate_page_requirements(payload))
        _validate_artifact_refs(payload, args.records_dir)

    if warnings:
        for warning in sorted(set(warnings)):
            print(f"Warning: {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
