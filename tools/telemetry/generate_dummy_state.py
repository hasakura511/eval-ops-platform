#!/usr/bin/env python3
"""Generate deterministic dummy Bureaucratic Autoregression telemetry snapshots."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str


SCENARIOS = [
    Scenario("nominal", "NOMINAL"),
    Scenario("deregulation", "DEREGULATION_TRIGGERED"),
    Scenario("high_entropy", "HIGH_ENTROPY"),
    Scenario("audit_fail", "AUDIT_FAIL"),
    Scenario("sandbox_exit", "SANDBOX_EXIT"),
    Scenario("critical_halt", "CRITICAL_HALT"),
]


def _timestamp_for(index: int, base: datetime) -> str:
    return (base + timedelta(hours=index)).isoformat().replace("+00:00", "Z")


def _artifact_id(base: str, suffix: str) -> str:
    return f"artifact:{base}@{suffix}"


def _hash_id(seed: str) -> str:
    return f"hash:{seed}"


def _build_state(t_index: int, scenario: Scenario, base_time: datetime) -> dict[str, Any]:
    t_label = f"t{t_index:06d}"
    status = scenario.label
    admin_ratio = 0.12
    beta = 0.2
    rule_entropy = 0.04
    disagreement_rate = 0.06
    drift_score = 0.12
    audit_passed = True
    accept_passed = True
    sandbox_mode = True
    command_type = "FREEZE"
    alerts: list[dict[str, Any]] = []

    if scenario.key == "deregulation":
        admin_ratio = 0.35
    elif scenario.key == "high_entropy":
        rule_entropy = 1.25
    elif scenario.key == "audit_fail":
        audit_passed = False
        accept_passed = False
        disagreement_rate = 0.6
        drift_score = 0.75
        alerts = [
            {
                "severity": "HIGH",
                "type": "GOODHART_DETECTED",
                "source": "Inspectorate-A",
                "message": "Audit failed due to drift between primary and audit metrics.",
                "evidence_refs": [
                    _artifact_id("audit", f"a-{t_label}"),
                    _artifact_id("x", f"{t_label}.1"),
                ],
            }
        ]
    elif scenario.key == "sandbox_exit":
        sandbox_mode = False
        command_type = "SANDBOX_CLOSE"
    elif scenario.key == "critical_halt":
        command_type = "HALT"
        alerts = [
            {
                "severity": "CRITICAL",
                "type": "SYSTEM_HALT",
                "source": "Executive",
                "message": "Critical halt issued pending audit recovery.",
                "evidence_refs": [
                    _artifact_id("decision", f"halt-{t_label}"),
                ],
            }
        ]

    return {
        "meta": {
            "project_id": "PROJ-ALPHA",
            "t": t_index,
            "timestamp": _timestamp_for(t_index, base_time),
            "global_status": status,
        },
        "B_t": {
            "H_t": {"org_chart_ref": _artifact_id("hierarchy", t_label)},
            "R_t": {
                "rules": [
                    {
                        "id": "R-017",
                        "text_ref": _artifact_id("rule", "R-017"),
                        "created_t": max(0, t_index - 12),
                        "expires_t": t_index + 12,
                        "owner_role": "Executive",
                        "risk_tier": "LOW",
                    }
                ],
                "rule_budget": {
                    "b": 1,
                    "current_count": 23,
                    "added_this_iter": 1,
                    "deleted_this_iter": 1,
                },
            },
            "A_t": {
                "units": [
                    {
                        "unit_id": "ops-07",
                        "mandate_ref": _artifact_id("mandate", "ops-07"),
                        "jurisdiction": "backend-dev",
                        "D_i": 0.35,
                        "discretion_spent_this_iter": 0.1,
                        "variance_memos": [_artifact_id("variance", "v-991")],
                    },
                    {
                        "unit_id": "audit-02",
                        "mandate_ref": _artifact_id("mandate", "audit-02"),
                        "jurisdiction": "security-audit",
                        "D_i": 0.25,
                        "discretion_spent_this_iter": 0.05,
                        "variance_memos": [],
                    },
                ]
            },
            "Pi_t": {
                "p": 0.15,
                "beta": beta,
                "r": 0.3,
                "w_t": [0.4, 0.3, 0.3],
                "lambda_t": 1.0,
                "mu_t": 0.5,
                "metric_rotation": {"active_profile": "M-03", "next_rotation_t": 45},
            },
            "L_t": {
                "ledger_head": _hash_id(f"abc{t_index:03d}"),
                "recent_artifacts": [_artifact_id("x", f"{t_label}.1")],
                "recent_decisions": [_artifact_id("decision", f"d-{t_label}")],
                "recent_audits": [_artifact_id("audit", f"a-{t_label}")],
                "recent_incidents": [f"incident:i-{t_label}"],
                "provenance_ref": _artifact_id("provenance", t_label),
            },
        },
        "topology": {
            "active_jurisdictions": [
                "backend-dev",
                "frontend-dev",
                "security-audit",
            ],
            "sandbox_mode": sandbox_mode,
            "sandbox_jurisdiction": "experimental-features",
        },
        "physics": {
            "admin_ratio": admin_ratio,
            "rule_entropy": rule_entropy,
            "goodhart": {
                "disagreement_rate": disagreement_rate,
                "drift_score": drift_score,
            },
            "risk_thermometer": 0.45,
        },
        "evaluation": {
            "g(x_t)": {
                "quality": 0.88,
                "correctness": 0.91,
                "usability": 0.72,
            },
            "Risk(x_t)": 0.18,
            "Overhead(x_t)": 0.17,
            "Accept(x_t)": accept_passed,
            "audit": {
                "audited": True,
                "AuditPassed": audit_passed,
                "audit_ref": _artifact_id("audit", f"a-{t_label}"),
            },
        },
        "registry": {
            "latest_block_hash": "0x9a7...",
            "pending_memos": 3,
            "amicus_briefs": 0,
        },
        "alerts": alerts,
        "commands": {
            "last_command": {
                "id": f"cmd-{900 + t_index}",
                "type": command_type,
                "acked": True,
                "acked_by": "bureaucracy-loop",
            }
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _collect_artifact_refs(payload: Any) -> Iterable[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("_ref") and isinstance(value, str) and value.startswith("artifact:"):
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
                        if isinstance(item, str) and item.startswith("artifact:"):
                            yield item
            yield from _collect_artifact_refs(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _collect_artifact_refs(item)


def _write_records(states: Iterable[dict[str, Any]], records_dir: Path) -> None:
    artifacts_dir = records_dir / "artifacts"
    provenance_dir = records_dir / "provenance"
    ledger_dir = records_dir / "ledger"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    provenance_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    artifacts: set[str] = set()
    provenance_refs: set[str] = set()
    ledger_heads: set[str] = set()

    for state in states:
        artifacts.update(_collect_artifact_refs(state))
        provenance_ref = state["B_t"]["L_t"]["provenance_ref"]
        if isinstance(provenance_ref, str):
            provenance_refs.add(provenance_ref)
        ledger_heads.add(state["B_t"]["L_t"]["ledger_head"])

    for ref in sorted(artifacts):
        artifact_id = ref.split("artifact:", 1)[1]
        payload = {"id": ref, "summary": "Stub artifact payload."}
        _write_json(artifacts_dir / f"{artifact_id}.json", payload)

    for ref in sorted(provenance_refs):
        provenance_id = ref.split("artifact:", 1)[1]
        payload = {"nodes": [], "edges": []}
        _write_json(provenance_dir / f"{provenance_id}.json", payload)

    for ref in sorted(ledger_heads):
        ledger_id = ref.split("hash:", 1)[1]
        payload = {"ledger_head": ref, "entries": []}
        _write_json(ledger_dir / f"{ledger_id}.json", payload)


def generate_snapshots(output_dir: Path, records_dir: Path, write_records: bool) -> list[dict[str, Any]]:
    base_time = datetime(2026, 1, 14, 14, 0, 0, tzinfo=timezone.utc)
    states: list[dict[str, Any]] = []

    for index, scenario in enumerate(SCENARIOS, start=1):
        state = _build_state(index, scenario, base_time)
        states.append(state)
        _write_json(output_dir / "history" / f"t={index:06d}.json", state)

    latest = states[-1]
    _write_json(output_dir / "latest.json", latest)

    if write_records:
        _write_records(states, records_dir)

    return states


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic telemetry snapshots.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("state"),
        help="Directory for latest.json and history snapshots.",
    )
    parser.add_argument(
        "--records-dir",
        type=Path,
        default=Path("records"),
        help="Directory for Records Office stub artifacts.",
    )
    parser.add_argument(
        "--skip-records",
        action="store_true",
        help="Skip writing records artifacts/provenance/ledger stubs.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    generate_snapshots(args.output_dir, args.records_dir, not args.skip_records)


if __name__ == "__main__":
    main()
