# LLM Quickstart

A fast, explicit index so an assistant can orient quickly and avoid unnecessary searching.

## Start here (90 seconds)
- Product goal and current phase: `README.md`.
- Full repo map: `docs/organization_plan.md`.
- What is done vs. planned: `docs/status_board.md`.

## Primary system artifacts
- UI snapshot contract: `docs/control_room_snapshot_v0.md`.
- UI contract: `docs/control_room_ui_contract_v0.md`.
- Dashboard mappings: `docs/dashboard_mapping.md`.
- Current snapshot data: `state/control_room_latest.json`.

## Run the UI quickly
```bash
python -m http.server 8001
```
Then open:
- http://localhost:8001/dashboard/workboard.html
- http://localhost:8001/dashboard/hierarchy.html

## Tooling and evaluation
- Tooling home: `tools/`.
- Hint evaluation CLI: `tools/hint_eval` (wrapper).
- Hint evaluation package: `tools/media_hint_eval/`.
- Baseline diffs: `records/baseline_diff/`.

## Tests and checks
- Contract tests: `python tools/contracts/contract_test.py`.
- Pytest: `pytest -q`.

## Rules of the repo
- Keep TODO drafts in `docs/todo/` only.
- Keep status updates in `docs/status_board.md`.
- Prefer linking to source docs over duplicating them.
