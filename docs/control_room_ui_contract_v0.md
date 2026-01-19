# ControlRoomSnapshot v0 (UI Contract)

**Purpose:** Provide a stable, additive JSON shape for the Control Room UI (Workboard + Hierarchy). The UI tolerates missing fields and renders “—” or empty states where data is absent.

## Snapshot sources (Phase 0)

- **Primary:** `state/control_room_latest.json` (static snapshot for dashboard pages).
- **Optional:** Query string override via `?source=../state/control_room_latest.json` or other snapshot paths under `/state`.
- **Static mode note:** `dashboard/state` is a symlink to `../state` so `python -m http.server` can serve `/state/*` fixtures from the dashboard directory.
- **Note:** Phase 0 is snapshot-driven. Phase 1 may swap sources to API/DB, but should preserve this shape (additive only).

## Live update modes (Phase 0)

**Preferred:** Server-Sent Events (SSE) stream with polling fallback.

- **SSE stream:** `GET /api/v1/control-room/stream`
  - Emits `event: snapshot` with full `ControlRoomSnapshot v0` JSON payloads.
  - Emits `event: ping` heartbeats every ~15s.
- **Snapshot endpoint:** `GET /api/v1/control-room/snapshot`
  - Returns the current snapshot JSON (file-backed).
  - Used by polling fallback or for first paint when running the backend.

## ControlRoomSnapshot v0 (top-level)

```json
{
  "schema_version": "control-room-snapshot-v0",
  "as_of": "2026-01-15T02:47:06.105947Z",
  "health": {
    "status": "Nominal",
    "data_freshness_seconds": 12,
    "active_alerts_count": 2
  },
  "projects": ["Project"],
  "alerts": ["Alert"]
}
```

### Field notes

- `as_of`: ISO timestamp for the snapshot.
- `health.status`: High-level label (Nominal / Warning / Critical).
- `health.data_freshness_seconds`: Seconds since last refresh. If omitted, UI derives freshness from `as_of`.
- `health.active_alerts_count`: Optional explicit count; defaults to `alerts.length`.

## Required vs optional fields

**Required (Phase 0 UI stability):**

- `schema_version` (string, recommended but tolerated if missing)
- `as_of` (timestamp)
- `projects` (array, can be empty)
- `alerts` (array, can be empty)

**Optional (UI will render placeholders if absent):**

- `health` (object)
- `projects[].tracks[]`
- `tracks[].runs[]`
- `runs[].owner`
- `runs[].metrics_summary[]`
- `runs[].artifact_refs[]`
- `runs[].todos[]`
- `alerts[].artifact_refs[]`

## Project

```json
{
  "project_id": "proj-atlas",
  "name": "Atlas QA",
  "status": "running",
  "tracks": ["Track"]
}
```

## Track

```json
{
  "track_id": "track-redteam",
  "type": "redteam",
  "name": "Adversarial / Red Team",
  "status": "running",
  "runs": ["Run"]
}
```

## Run

```json
{
  "run_id": "run-redteam-044",
  "status": "failed",
  "last_update_at": "2026-01-15T02:29:06.105947Z",
  "owner": {"Agent"},
  "failure_count": 3,
  "next_action": "Patch prompt filtering",
  "todos": ["Todo"],
  "metrics_summary": ["Metric"],
  "artifact_refs": ["ArtifactRef"]
}
```

## Agent (owner)

```json
{
  "agent_id": "agent-red-02",
  "display_name": "Red-02",
  "role": "attack",
  "status": "active"
}
```

## Todo

```json
{
  "todo_id": "todo-redteam-011",
  "title": "Reproduce jailbreak prompt",
  "status": "in_progress",
  "owner_agent_id": "agent-red-02",
  "updated_at": "2026-01-15T02:27:06.105947Z",
  "blocking_reason": "Waiting for trace artifact",
  "artifact_refs": ["ArtifactRef"]
}
```

## Metric

```json
{
  "name": "Exploit rate",
  "value": "18%",
  "unit": null
}
```

## Alert

```json
{
  "alert_id": "alert-022",
  "severity": "warn",
  "run_id": "run-redteam-044",
  "message": "Exploit resurfaced after patch; manual review required.",
  "timestamp": "2026-01-15T02:37:06.105947Z",
  "artifact_refs": ["ArtifactRef"]
}
```

## ArtifactRef

```json
{
  "artifact_id": "artifact-attack-77",
  "label": "attack payload",
  "href": "/records/artifacts/attack-77.json"
}
```

## Compatibility rules

- **Additive only:** New fields must not break existing UI.
- **Tolerant reads:** UI treats missing arrays as empty and missing scalars as “—”.
- **Stable IDs:** Use stable `project_id`, `track_id`, `run_id`, `todo_id`, `alert_id` when possible.
- **Legacy-safe:** Legacy snapshots are mapped into this shape by a client adapter; do not remove fields needed by the adapter.

## Legacy mapping (state/latest.json → v0)

| Legacy field | v0 field | Notes |
| --- | --- | --- |
| `meta.timestamp` | `as_of` | Used for snapshot time and freshness. |
| `meta.global_status` | `health.status` | Also mapped to run/track/project status. |
| `meta.project_id` | `projects[].project_id` | Used as the single legacy project id/name. |
| `B_t.A_t.units[]` | `projects[].tracks[].runs[]` | Units become runs under `track_id = legacy-units`. |
| `units[].variance_memos[]` | `runs[].failure_count` | Count of variance memos. |
| `units[].mandate_ref` | `runs[].next_action` / `runs[].artifact_refs[]` | Rendered as “Review …” action and artifact link. |
| `alerts[]` | `alerts[]` | Severity lowercased, evidence refs mapped to artifact links. |

## Data source priority & switching

1. **Primary:** `state/control_room_latest.json` (ControlRoomSnapshot v0)
2. **Fallback:** `state/latest.json` (legacy snapshot mapped to v0)
3. **Optional:** API endpoint (if configured)

**Switching sources:**

- `?source=../state/samples/control_room_empty.json` — override with any snapshot path.
- `?api=https://example.com/control-room-snapshot.json` — optional API endpoint (only if provided).
- `?stream=https://example.com/api/v1/control-room/stream` — override SSE stream endpoint.
- `?snapshot=https://example.com/api/v1/control-room/snapshot` — override snapshot endpoint.
