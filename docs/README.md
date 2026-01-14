# Bureaucratic Autoregression Control Room

## Generate dummy telemetry

```bash
python tools/telemetry/generate_dummy_state.py
```

This writes deterministic snapshots to `state/history/` and updates `state/latest.json`.

## Run contract tests

```bash
python tools/contracts/contract_test.py
```

The tests validate JSON schema compliance, dashboard field coverage, and Records Office resolution.

## View the dashboard locally

```bash
python -m http.server 8000
```

Then open <http://localhost:8000/dashboard/index.html> in a browser.
