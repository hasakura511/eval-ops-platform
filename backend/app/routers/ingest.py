import difflib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.submission import Submission
from app.schemas.ingest import (
    ApplyPatchResponse,
    IngestRequest,
    IngestResponse,
    ParsedError,
    ParsedPayload,
)
from app.services.verifier_engine import VerificationViolation, VerifierEngine

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

DEFAULT_RUBRIC_PATH = Path(__file__).resolve().parent.parent.parent / "rubrics" / "maps_evaluation.md"
BANNED_PHRASES = ["guess", "maybe", "probably", "i think"]


def _extract_sections(raw_text: str) -> Dict[str, str]:
    headers = ["debug info", "ratings table", "errors"]
    pattern = re.compile(r"^(debug info|ratings table|errors)\s*:?", re.IGNORECASE | re.MULTILINE)
    matches = list(pattern.finditer(raw_text))
    sections: Dict[str, str] = {}

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
        header = match.group(1).lower()
        sections[header] = raw_text[start:end].strip()

    # Fallback: if no headers matched, everything goes to debug info
    if not sections and raw_text.strip():
        sections["debug info"] = raw_text.strip()

    # Ensure keys exist
    for header in headers:
        sections.setdefault(header, "")
    return sections


def _parse_debug_info(section_text: str) -> Dict[str, Any]:
    fields = {
        "query": None,
        "result_being_evaluated": None,
        "result_address": None,
        "classification": None,
        "result_type": None,
        "distance_to_user_m": None,
        "distance_to_viewport_m": None,
        "viewport_status": None,
    }
    line_pattern = re.compile(r"^\s*([A-Za-z _]+)\s*[:|-]\s*(.+)$")

    for line in section_text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = line_pattern.match(line)
        if not match:
            continue
        raw_key = match.group(1).strip().lower().replace(" ", "_")
        value = match.group(2).strip()
        if raw_key in fields:
            if raw_key in {"distance_to_user_m", "distance_to_viewport_m"}:
                try:
                    fields[raw_key] = float(value)
                except ValueError:
                    fields[raw_key] = value
            else:
                fields[raw_key] = value

    return fields


def _parse_ratings_table(section_text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in section_text.splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 3:
            continue
        if parts[0].lower() == "field":
            continue
        rows.append({"field": parts[0], "answer": parts[1], "details": parts[2]})
    return rows


def _parse_errors(section_text: str) -> List[ParsedError]:
    cleaned = section_text.strip()
    if not cleaned:
        return []

    errors: List[ParsedError] = []
    # Try JSON first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    errors.append(ParsedError(**item))
        elif isinstance(parsed, dict):
            errors.append(ParsedError(**parsed))
        if errors:
            return errors
    except json.JSONDecodeError:
        pass

    # Fallback: parse line-based errors
    for idx, line in enumerate(cleaned.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|") if part.strip()]
        data: Dict[str, Any] = {"index": idx}
        for part in parts:
            lower = part.lower()
            if lower.startswith("field"):
                data["field"] = part.split(":", 1)[-1].strip() if ":" in part else part.replace("field", "", 1).strip()
            elif lower.startswith("from"):
                data["from_value"] = part.split(":", 1)[-1].strip()
            elif lower.startswith("to"):
                data["to_value"] = part.split(":", 1)[-1].strip()
            elif "checkbox" in lower:
                data["checkbox"] = part.split(":", 1)[-1].strip() if ":" in part else part
            elif "rationale" in lower:
                data["rationale_text"] = part.split(":", 1)[-1].strip()
        errors.append(ParsedError(**data))

    return errors


def _extract_artifact_refs(raw_text: str) -> List[str]:
    uuid_pattern = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
    return list({match.group(0) for match in uuid_pattern.finditer(raw_text)})


def _generate_unified_diff(rubric_path: Path, rules_to_add: List[str]) -> Tuple[str, Dict[str, Any]]:
    if not rubric_path.exists():
        raise HTTPException(status_code=404, detail=f"Rubric file not found at {rubric_path}")

    original_lines = rubric_path.read_text().splitlines()
    updated_lines = list(original_lines)

    if rules_to_add:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append("## Additional Rules")
        for rule in rules_to_add:
            updated_lines.append(rule)

    diff = "\n".join(
        difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile=str(rubric_path),
            tofile=f"{rubric_path} (patched)",
            lineterm="",
        )
    )

    return diff, {"rubric_path": str(rubric_path), "rules_to_add": rules_to_add}


def _generate_rubric_patch(errors: List[ParsedError], rubric_path: Path) -> Tuple[str, Dict[str, Any]]:
    rules_to_add: List[str] = []
    for err in errors:
        field = (err.field or "").strip().lower()
        rationale = (err.rationale_text or "").lower()
        to_value = (err.to_value or "").lower()

        if field == "pin accuracy" and "different business" in rationale:
            rules_to_add.append("- If visible label on satellite conflicts with result name → Pin Accuracy = Wrong")
        if field == "address accuracy" and to_value == "incorrect":
            rules_to_add.append("- Address Accuracy = Incorrect when pin resolves to different business")

    return _generate_unified_diff(rubric_path, rules_to_add)


def _run_verifiers(raw_text: str, artifact_refs: List[str]) -> List[Dict[str, Any]]:
    engine = VerifierEngine()
    artifacts = [{"id": ref, "artifact_type": "structured_output"} for ref in artifact_refs]
    execution = {"decision": {"rationale": raw_text}}
    results: List[Dict[str, Any]] = []

    configs = {"banned_phrases": {"phrases": BANNED_PHRASES}}
    for verifier_name in ["artifact_referenced", "observation_specificity", "banned_phrases"]:
        passed, violations = engine.verify(verifier_name, artifacts, execution, configs.get(verifier_name, {}))
        results.append(
            {
                "verifier": verifier_name,
                "passed": passed,
                "violations": [v.to_dict() if isinstance(v, VerificationViolation) else v for v in violations],
            }
        )

    return results


@router.post("/", response_model=IngestResponse)
def ingest_output(payload: IngestRequest, db: Session = Depends(get_db)):
    raw_text = payload.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text cannot be empty")

    sections = _extract_sections(raw_text)
    parsed_payload = ParsedPayload(
        debug_info=_parse_debug_info(sections.get("debug info", "")),
        ratings_table=_parse_ratings_table(sections.get("ratings table", "")),
        errors=_parse_errors(sections.get("errors", "")),
        artifact_refs=_extract_artifact_refs(raw_text),
    )

    patch_preview, patch_data = _generate_rubric_patch(parsed_payload.errors, DEFAULT_RUBRIC_PATH)
    verifier_results = _run_verifiers(raw_text, parsed_payload.artifact_refs)

    submission = Submission(
        raw_text=raw_text,
        parsed_json=json.loads(parsed_payload.model_dump_json()),
        artifact_refs=[uuid.UUID(ref) for ref in parsed_payload.artifact_refs],
        patch_preview=patch_preview,
        patch_data=patch_data,
        verifier_results=verifier_results,
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return IngestResponse(
        submission_id=str(submission.id),
        parsed=parsed_payload,
        patch_preview=patch_preview,
        verifier_violations=[result for result in verifier_results if not result["passed"]],
    )


def _apply_rules_to_rubric(rubric_path: Path, rules: List[str]) -> bool:
    if not rubric_path.exists():
        raise HTTPException(status_code=404, detail=f"Rubric file not found at {rubric_path}")

    lines = rubric_path.read_text().splitlines()
    existing = set(lines)
    added = False

    if rules:
        if "## Additional Rules" not in existing:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append("## Additional Rules")
            existing.add("## Additional Rules")
            added = True
        for rule in rules:
            if rule not in existing:
                if lines and lines[-1].strip() and lines[-1] != "## Additional Rules":
                    lines.append("")
                lines.append(rule)
                existing.add(rule)
                added = True

    if added:
        rubric_path.write_text("\n".join(lines) + "\n")
    return added


def _trigger_workflow_recompile():
    # Placeholder for triggering downstream recompilation
    return {"triggered": True}


@router.post("/{submission_id}/apply", response_model=ApplyPatchResponse)
def apply_patch(submission_id: str, db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    rubric_path = Path((submission.patch_data or {}).get("rubric_path", DEFAULT_RUBRIC_PATH))

    if submission.patch_applied:
        return ApplyPatchResponse(
            ok=True,
            rubric_path=str(rubric_path),
            applied_at=submission.patch_applied_at or datetime.utcnow(),
            already_applied=True,
        )

    rules_to_add = (submission.patch_data or {}).get("rules_to_add", [])
    changed = _apply_rules_to_rubric(rubric_path, rules_to_add)

    if changed:
        _trigger_workflow_recompile()

    submission.patch_applied = True
    submission.patch_applied_at = datetime.utcnow()
    db.add(submission)
    db.commit()

    return ApplyPatchResponse(
        ok=True,
        rubric_path=str(rubric_path),
        applied_at=submission.patch_applied_at,
        already_applied=not changed,
    )
