import difflib
import math
import re
import unicodedata
from typing import Dict, Optional, Tuple

from .schemas import Features, ScoreOutput


LABELS = [
    "Perfect",
    "Good",
    "Acceptable",
    "Unacceptable: Other",
    "Unacceptable: Spelling",
    "Unacceptable: Concerns",
    "Problem: Other",
]


def detect_mode(query: str) -> str:
    text = (query or "").strip()
    tokens = re.findall(r"[A-Za-z0-9']+", text)
    if len(text) <= 3 or len(tokens) <= 1:
        return "prefix"
    if tokens:
        last = tokens[-1]
        has_vowel = re.search(r"[aeiou]", last, re.IGNORECASE) is not None
        if len(last) <= 2 or (len(last) <= 4 and not has_vowel):
            return "prefix"
    return "intent"


def _strip_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_basic(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _normalize_punct(value: str) -> str:
    value = _strip_diacritics(value.casefold())
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def _detect_incomplete_title(official: str, result: str) -> bool:
    if not official or not result:
        return False
    separators = [":", "-", "–", "—"]
    for sep in separators:
        if sep in official:
            prefix = official.split(sep, 1)[0].strip()
            if _normalize_punct(prefix) == _normalize_punct(result):
                return True
    return False


def _detect_spelling_gate(result: str, official: Optional[str]) -> Tuple[bool, bool, bool]:
    if not result or not official:
        return False, False, False

    result_clean = result.strip()
    lower = result_clean.casefold()
    conversational = lower.startswith("any ") or lower.startswith("any") or lower.endswith("?")

    incomplete_title = _detect_incomplete_title(official, result_clean)
    if incomplete_title:
        return False, True, conversational

    if _normalize_basic(result_clean) == _normalize_basic(official):
        return False, False, conversational

    missing_punct = _normalize_punct(result_clean) == _normalize_punct(official)
    return missing_punct or conversational, False, conversational


def _detect_concerns(texts: Tuple[str, ...], keywords) -> bool:
    for text in texts:
        if not text:
            continue
        lowered = text.casefold()
        for keyword in keywords:
            if keyword in lowered:
                return True
    return False


def _compute_match_strength(result: str, official: Optional[str]) -> float:
    if not result or not official:
        return 0.0
    left = _normalize_punct(result)
    right = _normalize_punct(official)
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(a=left, b=right).ratio()


def _compute_popularity_entry(content_type: str, imdb_votes: Optional[int],
                              imdb_rating: Optional[float], starmeter: Optional[int],
                              config: dict) -> float:
    pop_cfg = config.get("popularity", {})
    max_votes = float(pop_cfg.get("max_votes", 1000000))
    rating_weight = float(pop_cfg.get("rating_weight", 0.4))
    votes_weight = float(pop_cfg.get("votes_weight", 0.6))
    category_score = float(pop_cfg.get("category_score", 0.35))

    if content_type == "person":
        starmeter_max = float(pop_cfg.get("starmeter_max", 500000))
        if starmeter is None:
            return 0.0
        rank = float(starmeter)
        return max(0.0, 1.0 - min(rank, starmeter_max) / starmeter_max)
    if content_type == "category":
        return category_score

    rating_score = 0.0
    if imdb_rating is not None:
        rating_score = max(0.0, min(float(imdb_rating) / 10.0, 1.0))

    votes_score = 0.0
    if imdb_votes is not None and imdb_votes > 0:
        votes_score = min(1.0, math.log10(imdb_votes) / math.log10(max_votes))

    return (rating_weight * rating_score) + (votes_weight * votes_score)


def _compute_popularity(features: Features, config: dict) -> float:
    return _compute_popularity_entry(
        features.content_type,
        features.imdb_votes,
        features.imdb_rating,
        features.starmeter,
        config,
    )


def _best_alternative_popularity(features: Features, config: dict) -> Tuple[float, Optional[dict]]:
    best = 0.0
    best_alt = None
    candidates = list(features.alternatives)
    if features.best_alternative and features.best_alternative not in candidates:
        candidates.append(features.best_alternative)
    for alt in candidates:
        pop = _compute_popularity_entry(
            alt.content_type,
            alt.imdb_votes,
            alt.imdb_rating,
            alt.starmeter,
            config,
        )
        if pop > best:
            best = pop
            best_alt = alt.model_dump()
    return best, best_alt


def _compute_dominance_ratio(popularity: float, alt_best: float) -> float:
    denom = popularity + alt_best
    if denom <= 0.0:
        return 0.0
    return popularity / denom


def _detect_sequel_penalty(result: str, query: str) -> bool:
    if not result:
        return False
    sequel_markers = [
        r"\b2\b",
        r"\b3\b",
        r"\b4\b",
        r"\bii\b",
        r"\biii\b",
        r"\biv\b",
        r"\bpart\s+2\b",
        r"\bpart\s+3\b",
        r"\bpart\s+4\b",
    ]
    if not any(re.search(marker, result, re.IGNORECASE) for marker in sequel_markers):
        return False
    if not query:
        return True
    return not any(re.search(marker, query, re.IGNORECASE) for marker in sequel_markers)


def _detect_category_not_title(official_title: Optional[str]) -> bool:
    if not official_title:
        return False
    lowered = official_title.casefold()
    return lowered.startswith("list of ") or "category:" in lowered


def _score_features(features: Features, config: dict) -> Tuple[float, Dict[str, float]]:
    weights = config.get("weights", {})
    match_weight = float(weights.get("match", 0.5))
    popularity_weight = float(weights.get("popularity", 0.3))
    dominance_weight = float(weights.get("dominance", 0.2))

    match_strength = _compute_match_strength(features.result, features.official_title)
    content_type = features.content_type
    if content_type == "unknown" and _detect_category_not_title(features.official_title):
        content_type = "category"
    popularity = _compute_popularity_entry(
        content_type,
        features.imdb_votes,
        features.imdb_rating,
        features.starmeter,
        config,
    )
    alt_best_popularity, best_alt = _best_alternative_popularity(features, config)
    dominance_ratio = _compute_dominance_ratio(popularity, alt_best_popularity)

    score = (match_weight * match_strength) + (popularity_weight * popularity) + (dominance_weight * dominance_ratio)

    sequel_penalty = 0.0
    if _detect_sequel_penalty(features.result, features.query):
        sequel_penalty = float(config.get("sequel_penalty", 0.0))
        score = max(0.0, score - sequel_penalty)

    return score, {
        "match_strength": match_strength,
        "popularity": popularity,
        "alt_best_popularity": alt_best_popularity,
        "dominance_ratio": dominance_ratio,
        "sequel_penalty": sequel_penalty,
        "best_alternative": best_alt,
    }


def _map_label(score: float, thresholds: dict) -> str:
    if score >= thresholds.get("perfect", 0.85):
        return "Perfect"
    if score >= thresholds.get("good", 0.7):
        return "Good"
    if score >= thresholds.get("acceptable", 0.55):
        return "Acceptable"
    return "Unacceptable: Other"


def _comment_for_rating(mode: str, rating: str, score: float, reason: str) -> str:
    basis = f"{mode} mode"
    detail = reason or f"score {score:.2f}"
    return f"{basis}: {detail}; rated {rating}."


def score_features(features: Features, config: dict) -> ScoreOutput:
    mode = detect_mode(features.query)
    thresholds = config.get("thresholds", {})
    concerns_keywords = config.get("concerns_keywords", [])

    concerns_gate = _detect_concerns(
        (features.result, features.official_title or "", " ".join(features.query_candidates)),
        concerns_keywords,
    )
    if concerns_gate:
        comment = _comment_for_rating(mode, "Unacceptable: Concerns", 0.0, "concerns keyword match")
        return ScoreOutput(
            task_id=features.task_id,
            rating="Unacceptable: Concerns",
            comment=comment,
            debug={
                "mode": mode,
                "gates": {"concerns": True, "validation": False, "spelling": False},
                "features": features.model_dump(),
                "score": 0.0,
                "thresholds": thresholds,
                "evidence_refs": features.evidence_refs,
            },
        )

    validation_failure = False
    if not features.result.strip():
        validation_failure = True
    has_fallback_validation = bool(features.official_title and features.content_type != "unknown")
    if not (features.result_imdb_ok or features.result_google_ok) and not has_fallback_validation:
        validation_failure = True
    if validation_failure:
        comment = _comment_for_rating(mode, "Problem: Other", 0.0, "validation failure")
        return ScoreOutput(
            task_id=features.task_id,
            rating="Problem: Other",
            comment=comment,
            debug={
                "mode": mode,
                "gates": {"concerns": False, "validation": True, "spelling": False},
                "features": features.model_dump(),
                "score": 0.0,
                "thresholds": thresholds,
                "evidence_refs": features.evidence_refs,
            },
        )

    spelling_gate, incomplete_title, conversational = _detect_spelling_gate(
        features.result, features.official_title
    )
    if spelling_gate:
        reason = "conversational filler" if conversational else "missing punctuation or diacritics"
        comment = _comment_for_rating(mode, "Unacceptable: Spelling", 0.0, reason)
        return ScoreOutput(
            task_id=features.task_id,
            rating="Unacceptable: Spelling",
            comment=comment,
            debug={
                "mode": mode,
                "gates": {"concerns": False, "validation": False, "spelling": True},
                "features": {**features.model_dump(), "incomplete_title": incomplete_title},
                "score": 0.0,
                "thresholds": thresholds,
                "evidence_refs": features.evidence_refs,
            },
        )

    score, components = _score_features(features, config)
    rating = _map_label(score, thresholds)

    incomplete_cfg = config.get("incomplete_title", {})
    if incomplete_title:
        upgrade = (
            components["dominance_ratio"] >= incomplete_cfg.get("upgrade_dominance", 0.85)
            and components["match_strength"] >= incomplete_cfg.get("upgrade_match", 0.9)
        )
        if not upgrade:
            rating = "Acceptable"

    dominance_cfg = config.get("dominance", {})
    min_votes_for_dominance = dominance_cfg.get("min_votes_for_dominance")
    low_vote_neutral = False
    dominance_valid = True
    best_alt_votes = None
    if components.get("best_alternative"):
        best_alt_votes = components["best_alternative"].get("imdb_votes")
    if min_votes_for_dominance is not None:
        if features.imdb_votes is not None and best_alt_votes is not None:
            if max(features.imdb_votes, best_alt_votes) < min_votes_for_dominance:
                low_vote_neutral = True
                dominance_valid = False
                components["dominance_ratio"] = 0.5

    if not dominance_valid:
        weights = config.get("weights", {})
        match_weight = float(weights.get("match", 0.5))
        popularity_weight = float(weights.get("popularity", 0.3))
        score = (match_weight * components["match_strength"]) + (popularity_weight * components["popularity"])
        if components.get("sequel_penalty"):
            score = max(0.0, score - components["sequel_penalty"])

    alt_margin = float(config.get("alt_margin", 0.2))
    alternative_min_pop = float(config.get("alt_min_popularity", 0.05))
    alternative_exists = False
    if not low_vote_neutral and components["alt_best_popularity"] > 0.0:
        if components["popularity"] <= 0.0:
            alternative_exists = components["alt_best_popularity"] >= alternative_min_pop
        else:
            alternative_exists = components["alt_best_popularity"] >= components["popularity"] * (1.0 + alt_margin)

    dominance_cutoffs = config.get("dominance_cutoffs", {})
    dom_perfect = dominance_cutoffs.get("perfect", 0.85)
    dom_good = dominance_cutoffs.get("good", 0.7)
    dom_acceptable = dominance_cutoffs.get("acceptable", 0.55)

    if dominance_valid:
        if components["dominance_ratio"] < dom_acceptable:
            rating = "Unacceptable: Other"
        elif mode == "prefix":
            if rating == "Perfect" and components["dominance_ratio"] < dom_perfect:
                rating = "Good"
            if alternative_exists or components["dominance_ratio"] < dom_good:
                if rating in ("Perfect", "Good"):
                    rating = "Acceptable"
        else:
            if rating == "Perfect" and components["dominance_ratio"] < dom_perfect:
                rating = "Good"
            elif rating in ("Perfect", "Good") and components["dominance_ratio"] < dom_good:
                rating = "Acceptable"
    elif mode == "prefix" and alternative_exists:
        if rating in ("Perfect", "Good"):
            rating = "Acceptable"

    niche_popularity = float(config.get("niche_popularity", 0.2))
    irrelevant_match = float(config.get("irrelevant_match_max", 0.6))
    category_not_title = _detect_category_not_title(features.official_title)
    niche = components["popularity"] < niche_popularity
    irrelevant = components["match_strength"] < irrelevant_match

    reason_order = [
        ("incomplete", incomplete_title),
        ("alternative exists", alternative_exists),
        ("niche", niche),
        ("sequel", components["sequel_penalty"] > 0.0),
        ("category-not-title", category_not_title),
        ("irrelevant", irrelevant),
    ]
    downgrade_reason = None
    if rating != "Perfect":
        for name, flag in reason_order:
            if flag:
                downgrade_reason = name
                break

    comment = _comment_for_rating(mode, rating, score, downgrade_reason or "scored")
    return ScoreOutput(
        task_id=features.task_id,
        rating=rating,
        comment=comment,
        debug={
            "mode": mode,
            "gates": {
                "concerns": False,
                "validation": False,
                "spelling": False,
                "incomplete_title": incomplete_title,
            },
            "features": {
                **features.model_dump(),
                **components,
                "alternative_exists": alternative_exists,
                "dominance_valid": dominance_valid,
                "category_not_title": category_not_title,
                "niche": niche,
                "irrelevant": irrelevant,
            },
            "score": score,
            "thresholds": thresholds,
            "evidence_refs": features.evidence_refs,
        },
    )
