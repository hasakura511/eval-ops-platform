import json
import os
import pytest

from tools.media_hint_eval.cli import cmd_join


def test_join_fixtures(tmp_path):
    out_path = tmp_path / "joined.jsonl"
    args = type("Args", (), {})()
    args.labeled = os.path.join("examples", "fixture_labeled.jsonl")
    args.features = "/tmp/features.fixtures.jsonl"
    args.out = str(out_path)
    args.label_field = "gold_rating"

    cmd_join(args)

    rows = []
    with open(out_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    assert len(rows) == 3
    assert rows[0]["label"]
    assert "features" in rows[0]


def test_join_missing_features(tmp_path):
    labeled_path = tmp_path / "labeled.jsonl"
    labeled_path.write_text('{"task_id":"missing","gold_rating":"Perfect"}\n', encoding="utf-8")

    features_path = tmp_path / "features.jsonl"
    features_path.write_text('{"task_id":"other"}\n', encoding="utf-8")

    args = type("Args", (), {})()
    args.labeled = str(labeled_path)
    args.features = str(features_path)
    args.out = str(tmp_path / "out.jsonl")
    args.label_field = "gold_rating"

    with pytest.raises(ValueError) as excinfo:
        cmd_join(args)

    assert "missing" in str(excinfo.value)
