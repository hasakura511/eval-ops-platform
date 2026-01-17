import os

from media_hint_eval.schemas import Features
from media_hint_eval.score import detect_mode, score_features
from media_hint_eval.utils import load_yaml


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "thresholds.yaml")


def test_mode_detection():
    assert detect_mode("ab") == "prefix"
    assert detect_mode("spider man") == "intent"
    assert detect_mode("spider m") == "prefix"


def test_spelling_gate_apostrophe():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t1",
        query="schindlers list",
        result="Schindlers List",
        official_title="Schindler's List",
        content_type="movie",
        imdb_votes=1500000,
        imdb_rating=8.9,
        query_candidates=["Schindler's List"],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.rating == "Unacceptable: Spelling"


def test_spelling_gate_diacritics():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t1b",
        query="amelie",
        result="Amelie",
        official_title="Amélie",
        content_type="movie",
        imdb_votes=700000,
        imdb_rating=8.3,
        query_candidates=["Amélie"],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.rating == "Unacceptable: Spelling"


def test_incomplete_title_exception():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t2",
        query="spider man",
        result="Spider Man",
        official_title="Spider-Man: Homecoming",
        content_type="movie",
        imdb_votes=800000,
        imdb_rating=7.4,
        query_candidates=["Spider-Man: Homecoming"],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.gates["incomplete_title"] is True
    assert output.rating == "Acceptable"


def test_conversational_filler_gate():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t3",
        query="any breaking bad?",
        result="Any Breaking Bad?",
        official_title="Breaking Bad",
        content_type="series",
        imdb_votes=1800000,
        imdb_rating=9.5,
        query_candidates=["Breaking Bad"],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.rating == "Unacceptable: Spelling"


def test_dominance_ratio_behavior():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t4",
        query="matrix",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=20000,
        imdb_rating=6.0,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 2500000,
                "imdb_rating": 8.0,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.features["alternative_exists"] is True


def test_alt_exists_threshold_behavior():
    config = load_yaml(CONFIG_PATH)
    config["alt_margin"] = 0.5
    features = Features(
        task_id="t4b",
        query="matrix",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=900000,
        imdb_rating=7.5,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 950000,
                "imdb_rating": 7.6,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.features["alternative_exists"] is False


def test_comment_reason_alternative_exists():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t4c",
        query="matrix",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=20000,
        imdb_rating=6.0,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 2500000,
                "imdb_rating": 8.0,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert "alternative exists" in output.comment


def test_weak_prefix_word_match_upgrade():
    config = load_yaml(CONFIG_PATH)
    config["weak_prefix"] = {"max_len": 2, "match_min": 0.8, "popularity_min": 0.2}
    features = Features(
        task_id="t4d-alt",
        query="e",
        result="Speak No Evil",
        official_title="Speak No Evil",
        content_type="movie",
        imdb_votes=127293,
        imdb_rating=6.8,
        query_candidates=["Speak No Evil"],
        alternatives=[
            {
                "name": "Eternals",
                "imdb_url": "https://www.imdb.com/title/tt9032400/",
                "content_type": "movie",
                "imdb_votes": 2500000,
                "imdb_rating": 8.0,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.rating == "Acceptable"
    assert output.debug.features["weak_prefix_upgrade"] is True
    assert "poorly related" in output.comment


def test_unpopular_prefix_upgrade():
    config = load_yaml(CONFIG_PATH)
    features = Features(
        task_id="t4d-unpopular",
        query="cruel",
        result="Cruel Peter",
        official_title="Cruel Peter",
        content_type="movie",
        imdb_votes=3527,
        imdb_rating=4.5,
        query_candidates=["Cruel Intentions"],
        alternatives=[
            {
                "name": "Cruel Intentions",
                "imdb_url": "https://www.imdb.com/title/tt0139134/",
                "content_type": "movie",
                "imdb_votes": 218203,
                "imdb_rating": 6.8,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.rating == "Acceptable"
    assert output.debug.features["unpopular_upgrade"] is True
    assert "niche" in output.comment


def test_low_vote_neutral_dominance():
    config = load_yaml(CONFIG_PATH)
    config["dominance"] = {"min_votes_for_dominance": 2000}
    features = Features(
        task_id="t4d",
        query="mat",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=500,
        imdb_rating=6.5,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 900,
                "imdb_rating": 6.9,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.features["dominance_ratio"] == 0.5
    assert output.debug.features["alternative_exists"] is False
    assert output.debug.features["dominance_valid"] is False
    assert "alternative exists" not in output.comment


def test_low_vote_no_dominance_downgrade():
    config = load_yaml(CONFIG_PATH)
    config["dominance"] = {"min_votes_for_dominance": 2000}
    features = Features(
        task_id="t4f",
        query="matrix",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=1500,
        imdb_rating=9.0,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 1800,
                "imdb_rating": 7.0,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.features["dominance_valid"] is False
    assert output.rating != "Unacceptable: Other"


def test_alt_exists_when_votes_high():
    config = load_yaml(CONFIG_PATH)
    config["dominance"] = {"min_votes_for_dominance": 2000}
    features = Features(
        task_id="t4e",
        query="mat",
        result="The Matrix",
        official_title="The Matrix",
        content_type="movie",
        imdb_votes=10000,
        imdb_rating=7.5,
        query_candidates=["The Matrix"],
        alternatives=[
            {
                "name": "The Matrix Reloaded",
                "imdb_url": "https://www.imdb.com/title/tt0234215/",
                "content_type": "movie",
                "imdb_votes": 1000000,
                "imdb_rating": 8.5,
                "starmeter": None,
                "source": "alt_imdb_1",
            }
        ],
        result_imdb_ok=True,
        evidence_refs={},
        errors=[],
    )
    output = score_features(features, config)
    assert output.debug.features["dominance_ratio"] < 0.5
    assert output.debug.features["alternative_exists"] is True
    assert "alternative exists" in output.comment
