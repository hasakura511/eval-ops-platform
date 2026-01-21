import os

from tools.media_hint_eval.extract import extract_cache
from tools.media_hint_eval.utils import read_jsonl


FIXTURE_CACHE = os.path.join(os.path.dirname(__file__), "fixtures", "cache")


def test_extract_cache(tmp_path):
    out_path = tmp_path / "features.jsonl"
    extract_cache(FIXTURE_CACHE, str(out_path))
    rows = read_jsonl(str(out_path))
    assert len(rows) == 3

    by_id = {row["task_id"]: row for row in rows}
    assert by_id["task-1"]["official_title"] == "Spider-Man: Homecoming"
    assert by_id["task-2"]["official_title"] == "Schindler's List"
    assert by_id["task-3"]["content_type"] == "movie"
