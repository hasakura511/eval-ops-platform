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
- Planning UI (workboard + hierarchy): `dashboard/`
- Snapshot data (UI contract): `state/control_room_latest.json`
- Snapshot spec: `docs/control_room_snapshot_v0.md`
- ATP streams + CLI: `docs/atp.md`

## Organization plan
See `docs/organization_plan.md` for a simple, flat map of where things live (including TODOs).

## Status board (done vs. planned)
See `docs/status_board.md` for a grouped view of what is done, what is still stubbed, and what is planned next.

## Intentionally stubbed (not implemented yet)
This is tracked in the status board so the "done vs. planned" view stays organized in one place.

## Changelog / What Changed (v1 vs v0)
- Shifted from backend-first API platform to UI-first explainable prototype.
- Added static Control Room dashboard pages driven by a snapshot JSON.
- Moved legacy API setup and workflow compiler docs to `README.v0.md`.

## License
MIT
