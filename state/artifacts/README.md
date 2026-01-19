# ATP artifacts

This folder stores content-addressed artifacts referenced from ATP packets.
Each artifact lives under `state/artifacts/<hash>/` with a manifest and the
attached files (diffs, logs, traces, screenshots, etc.).

Example structure:

```
state/artifacts/<hash>/
  manifest.json
  diff.patch
  logs.txt
  traces.jsonl
```
