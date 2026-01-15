#!/usr/bin/env python3
"""Generate a deterministic Control Room snapshot for the dashboard UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Metric:
    name: str
    value: str | float
    unit: str | None = None


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    label: str
    href: str


def isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_snapshot(as_of: datetime) -> dict[str, Any]:
    def ago(minutes: int) -> str:
        return isoformat(as_of - timedelta(minutes=minutes))

    def artifacts(prefix: str, run_id: str) -> list[ArtifactRef]:
        return [
            ArtifactRef(
                artifact_id=f"{prefix}-{run_id}-summary",
                label=f"{prefix} summary",
                href=f"/records/artifacts/{prefix}-{run_id}.json",
            ),
            ArtifactRef(
                artifact_id=f"{prefix}-{run_id}-ledger",
                label="ledger",
                href=f"/records/ledger/{prefix}-{run_id}.json",
            ),
        ]

    bilingual_run_id = "run-bilingual-021"
    redteam_run_id = "run-redteam-044"
    media_run_id = "run-media-003"

    snapshot = {
        "schema_version": "control-room-snapshot-v0",
        "as_of": isoformat(as_of),
        "health": {
            "status": "Nominal",
            "data_freshness_seconds": 12,
            "active_alerts_count": 2,
        },
        "projects": [
            {
                "project_id": "proj-atlas",
                "name": "Atlas QA",
                "status": "running",
                "tracks": [
                    {
                        "track_id": "track-bilingual",
                        "type": "bilingual",
                        "name": "API Bilingual Loop",
                        "status": "running",
                        "runs": [
                            {
                                "run_id": bilingual_run_id,
                                "status": "running",
                                "last_update_at": ago(4),
                                "owner": {
                                    "agent_id": "agent-ops-07",
                                    "display_name": "Ops-07",
                                    "role": "triage",
                                    "status": "active",
                                },
                                "failure_count": 1,
                                "next_action": "Re-run JA/EN alignment test",
                                "todos": [
                                    {
                                        "todo_id": "todo-bilingual-001",
                                        "title": "Verify tool call parity (JA→EN)",
                                        "status": "blocked",
                                        "owner_agent_id": "agent-ops-07",
                                        "updated_at": ago(6),
                                        "blocking_reason": "Waiting for trace artifact",
                                        "artifact_refs": [
                                            {
                                                "artifact_id": "artifact-trace-231",
                                                "label": "trace",
                                                "href": "/records/artifacts/trace-231.json",
                                            }
                                        ],
                                    },
                                    {
                                        "todo_id": "todo-bilingual-002",
                                        "title": "Draft next action memo",
                                        "status": "pending",
                                        "owner_agent_id": "agent-ops-07",
                                        "updated_at": ago(12),
                                        "blocking_reason": None,
                                        "artifact_refs": [],
                                    },
                                ],
                                "metrics_summary": [
                                    Metric(name="Parity", value="92%").__dict__,
                                    Metric(name="Tool error", value=0.12, unit="rate").__dict__,
                                ],
                                "artifact_refs": [ref.__dict__ for ref in artifacts("bilingual", bilingual_run_id)],
                            }
                        ],
                    },
                    {
                        "track_id": "track-redteam",
                        "type": "redteam",
                        "name": "Adversarial / Red Team",
                        "status": "running",
                        "runs": [
                            {
                                "run_id": redteam_run_id,
                                "status": "failed",
                                "last_update_at": ago(18),
                                "owner": {
                                    "agent_id": "agent-red-02",
                                    "display_name": "Red-02",
                                    "role": "attack",
                                    "status": "active",
                                },
                                "failure_count": 3,
                                "next_action": "Patch prompt filtering",
                                "todos": [
                                    {
                                        "todo_id": "todo-redteam-011",
                                        "title": "Reproduce jailbreak prompt",
                                        "status": "in_progress",
                                        "owner_agent_id": "agent-red-02",
                                        "updated_at": ago(20),
                                        "blocking_reason": None,
                                        "artifact_refs": [
                                            {
                                                "artifact_id": "artifact-attack-77",
                                                "label": "attack payload",
                                                "href": "/records/artifacts/attack-77.json",
                                            }
                                        ],
                                    }
                                ],
                                "metrics_summary": [
                                    Metric(name="Exploit rate", value="18%").__dict__,
                                    Metric(name="Coverage", value="64%").__dict__,
                                ],
                                "artifact_refs": [ref.__dict__ for ref in artifacts("redteam", redteam_run_id)],
                            }
                        ],
                    },
                ],
            },
            {
                "project_id": "proj-lyra",
                "name": "Lyra Research",
                "status": "running",
                "tracks": [
                    {
                        "track_id": "track-media",
                        "type": "media",
                        "name": "Media Research",
                        "status": "pending",
                        "runs": [
                            {
                                "run_id": media_run_id,
                                "status": "pending",
                                "last_update_at": ago(44),
                                "owner": {
                                    "agent_id": "agent-media-01",
                                    "display_name": "Media-01",
                                    "role": "research",
                                    "status": "idle",
                                },
                                "failure_count": 0,
                                "next_action": "Collect source pack",
                                "todos": [
                                    {
                                        "todo_id": "todo-media-004",
                                        "title": "Assemble reference bundle",
                                        "status": "pending",
                                        "owner_agent_id": "agent-media-01",
                                        "updated_at": ago(50),
                                        "blocking_reason": None,
                                        "artifact_refs": [],
                                    }
                                ],
                                "metrics_summary": [
                                    Metric(name="Sources", value=4, unit="items").__dict__,
                                ],
                                "artifact_refs": [ref.__dict__ for ref in artifacts("media", media_run_id)],
                            }
                        ],
                    }
                ],
            },
        ],
        "alerts": [
            {
                "alert_id": "alert-022",
                "severity": "warn",
                "run_id": redteam_run_id,
                "message": "Exploit resurfaced after patch; manual review required.",
                "timestamp": ago(10),
                "artifact_refs": [
                    {
                        "artifact_id": "artifact-attack-77",
                        "label": "attack payload",
                        "href": "/records/artifacts/attack-77.json",
                    }
                ],
            },
            {
                "alert_id": "alert-023",
                "severity": "info",
                "run_id": bilingual_run_id,
                "message": "Parity dipping below threshold in last run.",
                "timestamp": ago(3),
                "artifact_refs": [
                    {
                        "artifact_id": "artifact-trace-231",
                        "label": "trace",
                        "href": "/records/artifacts/trace-231.json",
                    }
                ],
            },
        ],
    }

    return json.loads(json.dumps(snapshot, default=lambda o: o.__dict__))


def main() -> None:
    output_path = Path(__file__).resolve().parents[2] / "state" / "control_room_latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = build_snapshot(datetime.now(timezone.utc))
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
