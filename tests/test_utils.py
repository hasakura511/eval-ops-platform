import os
import pytest

from media_hint_eval.utils import read_jsonl


def test_read_jsonl_skips_blank_lines():
    sample_path = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_labeled.jsonl")
    rows = read_jsonl(sample_path)
    assert len(rows) == 10


def test_read_jsonl_reports_line_numbers(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": 1}\n{bad json}\n', encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        read_jsonl(str(path))

    message = str(excinfo.value)
    assert "bad.jsonl" in message
    assert ":2:" in message
    assert "{bad json}" in message
