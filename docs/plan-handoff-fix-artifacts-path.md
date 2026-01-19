## Plan: handoff-fix-artifacts-path

### Goal
Make artifact storage default to a local-friendly path while keeping Docker's /app/artifacts behavior.

### Changes
- backend/app/core/config.py: switch STORAGE_PATH default to a local relative path so non-Docker runs work without env vars.

### Won't Do
- Change Docker compose or container mounts beyond existing env vars.
