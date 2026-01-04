import sys
from pathlib import Path

import pytest

# Ensure the backend package is importable when running tests from repository root
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.routers.ingest import _generate_unified_diff  # noqa: E402


def test_generate_unified_diff_adds_missing_header_and_rules(tmp_path: Path):
    rubric_path = tmp_path / "rubric.md"
    rubric_path.write_text("# Rubric\n")

    diff, _ = _generate_unified_diff(rubric_path, ["- New rule"])

    assert "+## Additional Rules" in diff
    assert "+- New rule" in diff


def test_generate_unified_diff_skips_existing_header_and_rules(tmp_path: Path):
    rubric_path = tmp_path / "rubric.md"
    rubric_path.write_text("# Rubric\n\n## Additional Rules\n- Existing rule\n")

    diff, _ = _generate_unified_diff(rubric_path, ["- Existing rule"])

    assert diff == ""
