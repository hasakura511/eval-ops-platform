# Status Board

A grouped view of what exists today versus what is planned or intentionally stubbed.

## Done (shipping today)
- UI-first Control Room dashboard (workboard + hierarchy) with explainable metrics and context.
- Static snapshot JSON contract for the Control Room UI.
- Deterministic snapshot generator for local demo data.
- Contract tests validating schema compliance and dashboard field coverage.

## Planned next (phased)
- Phase 1: Read-only snapshot endpoint (e.g., `GET /api/v1/control-room/snapshot`).
- Phase 2: Bilingual metrics and calibration guidance added to the snapshot contract.
- Phase 3: Run Detail view with explain panels for per-run artifacts and audits.

## Backlog (intentionally stubbed)
- Runner execution and task orchestration wiring.
- Database wiring/migrations for Control Room snapshots.
- Write actions from the UI (the dashboard remains read-only).
- Metrics formulas and thresholds beyond placeholders defined in the spec.
- Authentication, authorization, and multi-tenant routing.
