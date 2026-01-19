# RAMS-Style UI Review (Control Room)

## Scope

- `dashboard/workboard.html`
- `dashboard/hierarchy.html`
- `dashboard/assets/styles.css`
- `dashboard/assets/control_room.js`

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
- [ ] SSE updates apply when `state/control_room_latest.json` changes (LIVE mode).
- [ ] Polling fallback kicks in when SSE disconnects (POLLING mode).
- [ ] Drawer keyboard behavior verified (focus trap + ESC close).
- [ ] Staleness threshold verified (`STALE_THRESHOLD_SECONDS`).
- [ ] Empty/loading/error states verified (no runs, no alerts, fetch fail).
- [ ] Hierarchy scaling strategy stated (nested groups + scroll).
