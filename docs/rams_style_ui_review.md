# RAMS-Style UI Review (Control Room)

## Scope

- `dashboard/workboard.html`
- `dashboard/hierarchy.html`
- `dashboard/assets/styles.css`
- `dashboard/assets/control_room.js`

## PR Notes (Phase 0)

- Phase 0 is UI-only; SSE is file-backed; no DB changes.
- Data source priority: `control_room_latest` -> legacy (`state/latest.json`) -> optional API snapshot.

## Findings & Fixes

### Accessibility (A11y)

- **Issue:** Focus visibility was inconsistent across buttons, inputs, and links.
  - **Fix:** Added a consistent focus-visible ring across interactive elements and used semantic buttons/labels for filters and drawers.
- **Issue:** Panels lacked clear loading/error states, which can confuse screen readers and keyboard users.
  - **Fix:** Added explicit “Loading…” and “Snapshot unavailable” placeholders and ensured empty states are text-based.

### Readability & Consistency

- **Issue:** Spacing and color tokens were implicit, with repeated literal colors.
  - **Fix:** Introduced a global token system (`--space-*`, `--bg`, `--panel`, `--text`, `--muted`, etc.) and applied consistently.
- **Issue:** Status chips and badges were inconsistent in tone and hierarchy.
  - **Fix:** Consolidated chips, status pills, and alert severity styles into shared classes with consistent typography.

### Missing-State Coverage

- **Issue:** Panels did not always communicate data absence (no runs, no alerts, no hierarchy).
  - **Fix:** Each panel now renders a clear empty state, with a separate error state when snapshot loading fails.
- **Issue:** Stale data was not flagged explicitly.
  - **Fix:** Added a staleness indicator based on `health.data_freshness_seconds` or `as_of` and surfaced “Last refreshed.”

### Interaction & Resilience

- **Issue:** Workboard lacked a persistent detail view for long inspection.
  - **Fix:** Added a right-side drawer with keyboard focus trapping and ESC-to-close behavior.
- **Issue:** Filter state was not shareable via URL.
  - **Fix:** Sync filters to query parameters and apply on load.

## Remaining Risks / TODO

- **Keyboard focus order:** Should be re-validated with a real keyboard walk-through after adding more actions.
- **ARIA labels:** If additional controls are added, verify that labels and roles remain consistent and unambiguous.
- **Contrast checks:** Dark mode uses tokens, but high-contrast verification should be done with a contrast checker.

## Phase 0 Acceptance Checklist

- [x] Paths verified (workboard/hierarchy loading via `python -m http.server`).
- [x] SSE updates apply when `state/control_room_latest.json` changes (LIVE mode).
- [x] Polling fallback kicks in when SSE disconnects (POLLING mode).
- [ ] Drawer keyboard behavior verified (focus trap + ESC close).
- [ ] Staleness threshold verified (`STALE_THRESHOLD_SECONDS`).
- [x] Empty/loading/error states verified (no runs, no alerts, fetch fail).
- [ ] Hierarchy scaling strategy stated (nested groups + scroll).

## Verification Evidence

- Snapshot endpoint: `curl -i http://127.0.0.1:8000/api/v1/control-room/snapshot` → HTTP 200 with JSON payload.
- SSE stream: `content-type: text/event-stream`, `cache-control: no-cache`, heartbeat `event: ping` observed at ~15s.
- Change trigger: updating `state/control_room_latest.json` emitted a new `event: snapshot` with updated `as_of`.
- Static polling: Playwright opened workboard + hierarchy under `python -m http.server` and reported `POLLING`.
- Fetch failure: renaming `state/control_room_latest.json` + `state/latest.json` showed `OFFLINE` + error placeholders; console error count stayed flat across 18s; restoring files returned to `POLLING`.
- Empty states: `?source=state/samples/control_room_empty.json` showed "No runs match current filters.", "No hierarchy data available.", and "No alerts."
- Screenshots: `docs/screenshots/control-room-workboard.png`, `docs/screenshots/control-room-hierarchy.png`.
