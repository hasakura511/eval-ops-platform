import os
import pytest
import math

from tools.media_hint_eval.cli import _compute_metrics
from tools.media_hint_eval.utils import read_jsonl


def test_read_jsonl_skips_blank_lines():
    sample_path = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_labeled.jsonl")
    rows = read_jsonl(sample_path)
    assert len(rows) == 12


def test_read_jsonl_reports_line_numbers(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": 1}\n{bad json}\n', encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        read_jsonl(str(path))

    message = str(excinfo.value)
    assert "bad.jsonl" in message
    assert ":2:" in message
    assert "{bad json}" in message


def test_metrics_include_problem_other():
    labels = ["Perfect", "Good"]
    preds = ["Problem: Other", "Problem: Other"]
    metrics = _compute_metrics(preds, labels)
    assert "Problem: Other" in metrics["confusion"]
    assert metrics["confusion"]["Problem: Other"]["Problem: Other"] == 0
    assert metrics["confusion"]["Perfect"]["Problem: Other"] == 1


def test_metrics_support_only_macro_f1():
    labels = ["Acceptable", "Unacceptable: Spelling", "Unacceptable: Concerns"]
    preds = ["Acceptable", "Unacceptable: Spelling", "Unacceptable: Concerns"]
    metrics = _compute_metrics(preds, labels)
    assert math.isclose(metrics["accuracy"], 1.0, rel_tol=1e-6)
    assert math.isclose(metrics["macro_f1"], 3 / 7, rel_tol=1e-6)
    assert math.isclose(metrics["macro_f1_all_labels"], 3 / 7, rel_tol=1e-6)
    assert math.isclose(metrics["macro_f1_support_only"], 1.0, rel_tol=1e-6)
