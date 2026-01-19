# ATP Streams v0

This document describes the append-only ATP stream layout, packet fields, and minimal tooling for the Control Room UI.

## Directory layout

```
state/
  atp/
    index.json
    schema/
      atp_packet.schema.json
      atp_event.schema.json
    streams/
      <stream_id>/
        000001.request.atp
        000002.response.atp
        000003.review.atp
        events.jsonl
  artifacts/
    <hash>/
      manifest.json
      <files>
```

- `state/atp/streams/<stream_id>/` is append-only; never rewrite or delete packets/events.
- `state/atp/index.json` summarizes stream IDs, latest sequence, and packet filenames.
- `state/artifacts/<hash>/manifest.json` stores content-addressed evidence.

## Packet fields

Packet headers (required):

- `ATP`: protocol marker (`ATP/0.1`).
- `ID`: `<stream_id>/<seq>`.
- `TS`: ISO-8601 timestamp.
- `MODE`: `PLAN | EXEC | REVIEW`.
- `TASK`: task identifier.
- `STATE`: git state or environment marker.
- `PARENT`: previous packet ID or `null`.
- `ETAG`: content hash or `null`.
- `TOOLS`: array of tool labels.
- `APPROVAL`: `none | requested | granted_by_human`.
- `FAIL_CLASS`: `NONE | SPEC | ENV | TEST | LOGIC | INTEGRATION | DATA | TOOLING`.

Packet body (required unless noted):

- `goal` (string)
- `now[]` (list of strings)
- `next[]` (list of strings)
- `risks[]` (list of strings)
- `accept[]` (list of strings)
- `artifacts.manifests[]` (list of manifest paths)
- `questions[]` (list of strings)
- `confidence` (optional 0..1)

## CLI usage

Rebuild the stream index:

```bash
python tools/atp.py index --write
```

Create a new packet:

```bash
python tools/atp.py new --mode PLAN --task "control-room"
```

Append an event:

```bash
python tools/atp.py event --stream <stream_id> --type PLAN_CREATED --summary "created"
```

Approve a stream (human action):

```bash
python tools/atp.py approve --stream <stream_id> --rationale "approved to proceed"
```

Show a parsed packet:

```bash
python tools/atp.py show state/atp/streams/<stream_id>/000001.request.atp
```

## Snapshot builder

Generate `state/control_room_latest.json` deterministically from streams:

```bash
python tools/build_snapshot.py --output state/control_room_latest.json
```

The snapshot includes a `streams[]` array with the latest packet, status, and approval state for each stream.

## Approval behavior

- EXEC packets default to `APPROVAL: requested`.
- Human approvals append a REVIEW packet with `APPROVAL: granted_by_human`.
- Approval is append-only and recorded as both a packet and an event.
