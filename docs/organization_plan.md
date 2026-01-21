# Organization Plan

A flat, explicit map of where things live so the repo feels like a clean desk.

## Top-level map
- `dashboard/`: UI pages and assets (workboard + hierarchy).
- `docs/`: Documentation and specs (see sections below).
- `state/`: Snapshot JSON inputs for the UI.
- `tools/`: Scripts (telemetry generation, contract tests, utilities).
- `backend/`: API stubs and service scaffolding.
- `tests/`: Automated tests and fixtures.
- `examples/`, `schemas/`, `records/`, `config/`: Supporting assets and data.

## TODOs (single place)
- `docs/todo/`: All TODO drafts and backlog notes live here.
- If a TODO does not fit elsewhere, place it here instead of scattering it across the repo.

## Specs and contracts
- Snapshot contract: `docs/control_room_snapshot_v0.md`.
- UI contract: `docs/control_room_ui_contract_v0.md`.
- Dashboard mapping: `docs/dashboard_mapping.md`.

## How to run
- Root quick-start: `README.md`.
- Docs quick-start: `docs/README.md`.

## Rules of the desk
- Keep status in `docs/status_board.md` (done vs. planned vs. stubbed).
- Keep TODO drafts in `docs/todo/` only.
- Prefer linking to source docs over duplicating them.
