# Control Room Snapshot v0 (UI Contract)

This document defines the **UI-only** snapshot contract consumed by the Control Room Workboard and Hierarchy screens. It is intentionally minimal, additive, and tolerant of missing fields. It is **not** a database schema.

## Goals

- Drive **both** Workboard (portrait) and Hierarchy (ultra-wide) from one snapshot file.
- Keep the contract flexible so a future DB/API can populate it without changing the UI.
- Allow offline/static usage via a JSON file in `/state`.

## Snapshot Shape

```json
{
  "schema_version": "control-room-snapshot-v0",
  "as_of": "2024-01-05T12:00:00Z",
  "health": {
    "status": "Nominal",
    "data_freshness_seconds": 12,
    "active_alerts_count": 2
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
              "run_id": "run-bilingual-021",
              "status": "running",
              "last_update_at": "2024-01-05T11:58:10Z",
              "owner": {
                "agent_id": "agent-ops-07",
                "display_name": "Ops-07",
                "role": "triage",
                "status": "active"
              },
              "failure_count": 1,
              "next_action": "Re-run JA/EN alignment test",
              "todos": [
                {
                  "todo_id": "todo-bilingual-001",
                  "title": "Verify tool call parity (JA→EN)",
                  "status": "blocked",
                  "owner_agent_id": "agent-ops-07",
                  "updated_at": "2024-01-05T11:50:00Z",
                  "blocking_reason": "Waiting for trace artifact",
                  "artifact_refs": [
                    {
                      "artifact_id": "artifact-trace-231",
                      "label": "trace",
                      "href": "/records/artifacts/trace-231.json"
                    }
                  ]
                }
              ],
              "metrics_summary": [
                { "name": "Parity", "value": "92%" },
                { "name": "Tool error", "value": 0.12, "unit": "rate" }
              ],
              "artifact_refs": [
                {
                  "artifact_id": "bilingual-run-bilingual-021-summary",
                  "label": "bilingual summary",
                  "href": "/records/artifacts/bilingual-run-bilingual-021.json"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "alerts": [
    {
      "alert_id": "alert-022",
      "severity": "warn",
      "run_id": "run-redteam-044",
      "message": "Exploit resurfaced after patch; manual review required.",
      "timestamp": "2024-01-05T11:50:00Z",
      "artifact_refs": [
        {
          "artifact_id": "artifact-attack-77",
          "label": "attack payload",
          "href": "/records/artifacts/attack-77.json"
        }
      ]
    }
  ]
}
```

## Field Meaning (Minimum UI Requirements)

### Top-level
- `schema_version`: fixed identifier for UI contract compatibility.
- `as_of`: ISO-8601 timestamp for when the snapshot was captured.
- `health`: status fields used in the header.
- `projects[]`: tree of projects → tracks → runs → todos.
- `alerts[]`: recent alerts for the alerts rail.

### Project
- `project_id`, `name`, `status`: used in headers and hierarchy nodes.
- `tracks[]`: collection of tracks.

### Track
- `track_id`, `type`, `name`, `status`: displayed in hierarchy and filters.
- `runs[]`: list of active or recent runs.

### Run
- `run_id`, `status`, `last_update_at`: displayed on cards and hierarchy nodes.
- `owner`: used for ownership display and hierarchy agent node.
- `failure_count`, `next_action`: used in Workboard and spotlight.
- `todos[]`: expandable list and todo feed.
- `metrics_summary[]`: compact chips in Workboard.
- `artifact_refs[]`: optional run-level artifacts.

### Todo
- `todo_id`, `title`, `status`, `updated_at`: displayed in the drawer + feed.
- `owner_agent_id`, `blocking_reason`: used in Workboard detail.
- `artifact_refs[]`: optional evidence links.

### Alert
- `alert_id`, `severity`, `run_id`, `message`, `timestamp`: displayed in alert rail.
- `artifact_refs[]`: optional evidence links.

## Guarantees
- The snapshot is **read-only** and intended for polling.
- All arrays may be empty but should be present when possible.
- `schema_version` will only change on breaking updates.

## Non-Guarantees
- IDs are not stable across environments unless explicitly seeded.
- Missing fields are allowed; UI must show `—` or empty states.
- Artifact links may be placeholders until real storage integration exists.

## Future Production Source (Phase 1+)
This snapshot will be produced by a lightweight adapter that composes data from either:
- a database (runs, owners, todos, alerts),
- the artifact store (artifact refs), or
- the telemetry log (if `state.json` snapshots remain the source of truth).

The UI will remain unchanged and will continue polling the same snapshot endpoint or file.
