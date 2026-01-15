# Eval Ops Platform v1 (UI-First Explainable Prototype)

This repo is now centered on an explainable Control Room UI prototype that documents what each metric and widget is for, why it exists, and how it connects to runners, ledgers, artifacts, judges, and humans. The UI is a planning document first; backend wiring and execution systems are intentionally stubbed in this phase.

## UI-first explainable prototype
- Make every displayed number teach its purpose, inputs, and failure modes.
- Surface open questions and assumptions so the team can resolve them.
- Keep data flow anchored to a single snapshot JSON contract.

## Run the dashboard locally
From the repo root:
```bash
python3 -m http.server 8001
```
Then open:
- http://localhost:8001/dashboard/workboard.html
- http://localhost:8001/dashboard/hierarchy.html

If port 8001 is in use, pick another free port.

## Where things live
- Planning UI: `dashboard/` (workboard + hierarchy)
- Snapshot data: `state/control_room_latest.json` (UI contract)
- Snapshot spec: `docs/control_room_snapshot_v0.md`

## Intentionally stubbed (not implemented yet)
- No runner execution or task orchestration.
- No DB wiring or migrations for the Control Room snapshot.
- No write actions from the UI (it is read-only).
- Metrics formulas and thresholds are placeholders until defined in the spec.
- Authentication, authorization, and multi-tenant routing.

## Next phases
- Phase 1: Wire a read-only snapshot endpoint (e.g., GET /api/v1/control-room/snapshot).
- Phase 2: Add bilingual metrics and calibration guidance to the snapshot contract.
- Phase 3: Add a Run Detail view with explain panels for per-run artifacts and audits.

## Changelog / What Changed (v1 vs v0)
- Shifted from backend-first API platform to UI-first explainable prototype.
- Added static Control Room dashboard pages driven by a snapshot JSON.
- Moved legacy API setup and workflow compiler docs to `README.v0.md`.

## License
MIT
