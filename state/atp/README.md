# ATP state ledger

This folder stores append-only Agent Transfer Protocol (ATP) packets and stream
indexes for audit and RCA.

## Layout

- `index.json`: quick lookup for stream metadata and latest sequence.
- `schema/`: JSON Schemas for packets and events.
- `examples/`: canonical packet examples (text + JSON).
- `streams/<stream_id>/`: append-only packets and event log.
  - `000001.request.atp` / `000001.response.atp`
  - `events.jsonl`

## Usage

Create packets and events with `python tools/atp.py`:

- `python tools/atp.py new --mode PLAN --task my-task`
- `python tools/atp.py etag state/atp/streams/<id>/000001.request.atp`
- `python tools/atp.py event --stream <id> --type PLAN_CREATED --summary "..."`
- `python tools/atp.py bundle --stream <id> --kind diff --in path/to/diff.patch`

Schemas live in `state/atp/schema/` and examples in `state/atp/examples/`.
