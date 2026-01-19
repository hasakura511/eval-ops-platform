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
    "Unacceptable: Extra Language",
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


# Japan-specific writing system detection (JP01-JP06)
def _detect_writing_system(text: str) -> dict:
    """
    Detect Japanese writing systems present in text.

    Returns dict with counts of:
    - hiragana: ぁ-ん characters
    - katakana: ァ-ン characters
    - kanji: CJK unified ideographs
    - ascii: Latin/ASCII characters
    - numbers_arabic: 0-9
    - numbers_kanji: 一二三四五六七八九十百千万
    """
    if not text:
        return {"hiragana": 0, "katakana": 0, "kanji": 0, "ascii": 0,
                "numbers_arabic": 0, "numbers_kanji": 0}

    hiragana = len(re.findall(r'[\u3040-\u309F]', text))
    katakana = len(re.findall(r'[\u30A0-\u30FF]', text))
    # CJK Unified Ideographs (common kanji range)
    kanji = len(re.findall(r'[\u4E00-\u9FFF]', text))
    ascii_chars = len(re.findall(r'[A-Za-z]', text))
    numbers_arabic = len(re.findall(r'[0-9]', text))
    numbers_kanji = len(re.findall(r'[一二三四五六七八九十百千万億]', text))

    return {
        "hiragana": hiragana,
        "katakana": katakana,
        "kanji": kanji,
        "ascii": ascii_chars,
        "numbers_arabic": numbers_arabic,
        "numbers_kanji": numbers_kanji,
    }


def _is_japanese_content(text: str) -> bool:
    """Check if text contains Japanese writing systems."""
    if not text:
        return False
    ws = _detect_writing_system(text)
    return (ws["hiragana"] + ws["katakana"] + ws["kanji"]) > 0


def _detect_jp_writing_mismatch(result: str, official: Optional[str]) -> Tuple[bool, str]:
    """
    JP04/JP05: Detect if result uses wrong writing system compared to official title.

    Returns: (has_mismatch, mismatch_type)
    - has_mismatch: True if writing system doesn't match official
    - mismatch_type: Description of the mismatch (e.g., "hiragana instead of kanji")
    """
    if not result or not official:
        return (False, "")

    # Only apply to content with Japanese characters
    if not _is_japanese_content(official):
        return (False, "")

    result_ws = _detect_writing_system(result)
    official_ws = _detect_writing_system(official)

    # Check for writing system substitutions
    # JP05: Wrong writing system → Acceptable
    mismatches = []

    # Kanji in official but hiragana/katakana in result
    if official_ws["kanji"] > 0 and result_ws["kanji"] == 0:
        if result_ws["hiragana"] > 0 or result_ws["katakana"] > 0:
            mismatches.append("kana instead of kanji")

    # Hiragana in official but katakana in result (or vice versa)
    if official_ws["hiragana"] > 0 and result_ws["hiragana"] == 0 and result_ws["katakana"] > 0:
        mismatches.append("katakana instead of hiragana")
    if official_ws["katakana"] > 0 and result_ws["katakana"] == 0 and result_ws["hiragana"] > 0:
        mismatches.append("hiragana instead of katakana")

    # JP03: Japanese content in English but Katakana demoted
    # If official is English (ASCII) but result is Katakana
    if official_ws["ascii"] > 0 and official_ws["katakana"] == 0:
        if result_ws["katakana"] > 0 and result_ws["ascii"] == 0:
            mismatches.append("katakana instead of english")

    if mismatches:
        return (True, "; ".join(mismatches))
    return (False, "")


def _detect_jp_number_format_mismatch(result: str, official: Optional[str]) -> bool:
    """
    JP06: Detect number format mismatch (Arabic vs Kanji numbers).

    Returns True if result uses alternative number format (should be Good, not Perfect).
    """
    if not result or not official:
        return False

    result_ws = _detect_writing_system(result)
    official_ws = _detect_writing_system(official)

    # If official has Arabic numbers but result has Kanji numbers (or vice versa)
    if official_ws["numbers_arabic"] > 0 and result_ws["numbers_kanji"] > 0:
        return True
    if official_ws["numbers_kanji"] > 0 and result_ws["numbers_arabic"] > 0:
        return True

    return False


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


def _is_non_title_format(text: str) -> bool:
    """Detect conversational/question format that isn't a valid title."""
    if not text:
        return False
    lower = text.strip().casefold()
    # Question format
    if lower.endswith("?"):
        return True
    # Conversational filler
    if lower.startswith("any "):
        return True
    # Sentence-like (contains common filler words in sentence positions)
    sentence_patterns = [
        r"^(any|some|the best|a good|find|show me|looking for)\b",
        r"\b(that|which|featuring|with|about|on)\b.*\b(movies?|films?|shows?|series)\b",
        r"\bmovies?\s+that\b",
        r"\bfilms?\s+that\b",
        r"\bcontent\s+on\b",
    ]
    for pattern in sentence_patterns:
        if re.search(pattern, lower):
            return True
    return False


def _detect_diacritics_mismatch(result: str, official: str) -> bool:
    """Detect if result matches official but is missing diacritics."""
    if not result or not official:
        return False

    result_norm = _normalize_punct(result)

    # Check full title match (stripped diacritics match but original doesn't)
    official_norm = _normalize_punct(official)
    if result_norm == official_norm:
        # They match when normalized, check if original has diacritics
        if _strip_diacritics(official) != official:
            return True

    # Check if result matches a word in official title
    # e.g., "amelie" matches "Amélie" from "Le fabuleux destin d'Amélie Poulain"
    words = re.findall(r"[A-Za-zÀ-ÿ']+", official)
    for word in words:
        word_norm = _normalize_punct(word)
        if word_norm and word_norm == result_norm:
            # Check if the original word has diacritics
            if _strip_diacritics(word) != word:
                return True

    return False


def _detect_spelling_gate(result: str, official: Optional[str], is_category: bool = False) -> Tuple[bool, bool, bool, bool]:
    """
    Detect spelling/format issues.

    Returns:
        (spelling_gate, incomplete_title, conversational, non_title_format)
    """
    if not result or not official:
        return False, False, False, False

    result_clean = result.strip()
    lower = result_clean.casefold()
    conversational = lower.startswith("any ") or lower.endswith("?")
    non_title_format = _is_non_title_format(result_clean)

    # Category results are NOT spelling errors even if they look like non-title format
    if is_category:
        non_title_format = False
        conversational = False

    incomplete_title = _detect_incomplete_title(official, result_clean)
    if incomplete_title:
        return False, True, conversational, non_title_format

    if _normalize_basic(result_clean) == _normalize_basic(official):
        return False, False, conversational, non_title_format

    # Check for diacritics mismatch
    diacritics_mismatch = _detect_diacritics_mismatch(result_clean, official)
    if diacritics_mismatch:
        return True, False, conversational, non_title_format

    # Check punctuation-only difference
    missing_punct = _normalize_punct(result_clean) == _normalize_punct(official)
    return missing_punct or conversational or non_title_format, False, conversational, non_title_format


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


def _compute_prefix_match_strength(query: str, result: str, official: Optional[str]) -> tuple:
    """
    Compute prefix match strength on 0-2 scale per rubric.

    Returns: (strength, is_secondary_match)
    - strength 0: Irrelevant - result doesn't relate to query prefix at all
    - strength 1: Related - result matches query but imperfectly
    - strength 2: Strong - result starts with query and official title confirms match
    - is_secondary_match: True if match is on non-first word (poorly related)
    """
    if not query or not result:
        return (0, False)

    query_norm = _normalize_punct(query)
    result_norm = _normalize_punct(result)
    official_norm = _normalize_punct(official) if official else ""

    # Extract words from original strings (before punct removal) for word-level matching
    result_words = [_normalize_punct(w) for w in re.findall(r"[A-Za-z0-9']+", result)]
    official_words = [_normalize_punct(w) for w in re.findall(r"[A-Za-z0-9']+", official)] if official else []

    # Check if query matches first word (strong prefix match candidate)
    first_word_match = False
    if result_norm.startswith(query_norm):
        first_word_match = True
    elif result_words and result_words[0].startswith(query_norm):
        first_word_match = True

    # Check if query matches a secondary word (weak/poorly related match)
    secondary_word_match = False
    if not first_word_match:
        # Check result words
        for word in result_words[1:]:  # Skip first word
            if word.startswith(query_norm):
                secondary_word_match = True
                break
        # Check official title words
        if not secondary_word_match:
            for word in official_words[1:]:  # Skip first word
                if word.startswith(query_norm):
                    secondary_word_match = True
                    break

    # If no match at all, irrelevant
    if not first_word_match and not secondary_word_match:
        return (0, False)

    # If only secondary word match, return 1 (related but weak)
    if secondary_word_match and not first_word_match:
        return (1, True)  # Secondary match is poorly related

    # Check if official title matches (strong match)
    if official_norm:
        # Strong match: official title starts with query and result matches official
        official_starts = official_norm.startswith(query_norm)
        result_matches_official = result_norm == official_norm or result_norm in official_norm

        # Also check first word of official
        if official_words and official_words[0].startswith(query_norm):
            official_starts = True

        if official_starts and result_matches_official:
            return (2, False)

        # Check similarity
        similarity = difflib.SequenceMatcher(a=result_norm, b=official_norm).ratio()
        if similarity >= 0.8:
            return (2, False)

    # Default to related match (first word partial match)
    return (1, False)


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


def _detect_sequel_penalty(result: str, query: str, official_title: Optional[str] = None) -> bool:
    """
    Detect if a sequel result should be penalized.

    CT02: Consider franchise context - don't penalize if query matches franchise name.
    E.g., "ave" matching "Avengers: Endgame" should NOT be penalized because
    the user is searching for the Avengers franchise.
    """
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
    # If query explicitly includes sequel marker, no penalty
    if any(re.search(marker, query, re.IGNORECASE) for marker in sequel_markers):
        return False

    # CT02: Check if query matches the franchise name (prefix of result/title)
    # E.g., "ave" matches "Avengers" in "Avengers: Endgame"
    query_norm = _normalize_punct(query)
    result_norm = _normalize_punct(result)

    # Check if query is a prefix of the result (franchise match)
    if result_norm.startswith(query_norm):
        return False  # Query matches franchise, no penalty

    # Check against official title too
    if official_title:
        official_norm = _normalize_punct(official_title)
        if official_norm.startswith(query_norm):
            return False  # Query matches franchise, no penalty

        # Also check first word of title (franchise name often first)
        title_words = [_normalize_punct(w) for w in re.findall(r"[A-Za-z0-9']+", official_title)]
        if title_words and title_words[0].startswith(query_norm):
            return False  # Query matches franchise first word

    # Penalty applies only if query doesn't relate to franchise
    return True


def _detect_category_not_title(official_title: Optional[str]) -> bool:
    if not official_title:
        return False
    lowered = official_title.casefold()
    return lowered.startswith("list of ") or "category:" in lowered


def _weak_prefix_word_match(query: str, official_title: Optional[str], max_len: int) -> bool:
    if not query or not official_title:
        return False
    query = query.strip().casefold()
    if not query or len(query) > max_len:
        return False
    words = re.findall(r"[A-Za-z0-9']+", official_title)
    if not words:
        return False
    for idx, word in enumerate(words):
        if idx == 0:
            continue
        if word.casefold().startswith(query):
            return True
    return False


def _is_complex_hint(text: str) -> bool:
    """
    Detect if a hint is complex (multi-aspect) which should cap at Good.

    Complex hints have multiple qualifying conditions, such as:
    - "action movies with superheroes"
    - "romantic comedies from the 90s"
    - "movies that are both funny and scary"
    """
    if not text:
        return False
    lower = text.strip().casefold()

    # Multiple modifier indicators
    complexity_patterns = [
        r"\b(with|featuring|about|starring)\b.*\b(and|or|that)\b",  # chained conditions
        r"\bthat\s+are\b.*\band\b",  # "that are X and Y"
        r"\b(both|also|as well as)\b",  # explicit multi-aspect
        r"\b(from\s+the|in\s+the)\b.*\b(with|featuring|about)\b",  # era + condition
        r"(movies?|films?|shows?)\s+that\s+\w+\s+and\s+\w+",  # "movies that X and Y"
    ]

    for pattern in complexity_patterns:
        if re.search(pattern, lower):
            return True

    # Word count heuristic: very long hints are usually complex
    word_count = len(re.findall(r"\w+", lower))
    if word_count >= 8:
        return True

    return False


def _detect_category_result(result: str, query: str) -> bool:
    """
    Detect if result is a category/genre description rather than a specific title.

    Category results are valid completions like "disney+ animation" for query "ani"
    that describe a genre/category rather than pointing to a specific title.

    Note: Question format (ending with "?") is NOT a valid category - it's Extra Language.
    """
    if not result:
        return False

    result_lower = result.strip().casefold()
    query_lower = (query or "").strip().casefold()

    # Question format is NOT a valid category - it's verbose/Extra Language
    if result_lower.endswith("?"):
        return False

    # Check if result contains category indicators
    category_indicators = [
        r"\banimation\b",
        r"\banimated\b",
        r"\baction\s+movies?\b",
        r"\bcomedy\s+movies?\b",
        r"\bhorror\s+movies?\b",
        r"\bdrama\s+movies?\b",
        r"\bdisney\+?\b.*\b(movies?|shows?|series|animation)\b",
        r"\bnetflix\b.*\b(movies?|shows?|series|originals?)\b",
        r"\bmovies?\s+(that|with|featuring|about)\b",
        r"\bfilms?\s+(that|with|featuring|about)\b",
        r"\bsuperheroes?\b",
        r"\baction\b.*\bsuperheroes?\b",
    ]

    for pattern in category_indicators:
        if re.search(pattern, result_lower):
            # Verify the result relates to the query
            if query_lower and query_lower in result_lower:
                return True
            # Check if query is a prefix of any word in result
            words = re.findall(r"[a-z0-9]+", result_lower)
            for word in words:
                if word.startswith(query_lower):
                    return True
    return False


def _score_features(features: Features, config: dict, mode: str = "prefix") -> Tuple[float, Dict[str, float]]:
    weights = config.get("weights", {})
    match_weight = float(weights.get("match", 0.5))
    popularity_weight = float(weights.get("popularity", 0.3))
    dominance_weight = float(weights.get("dominance", 0.2))

    match_strength = _compute_match_strength(features.result, features.official_title)

    # Compute prefix-specific match strength (0-2 scale)
    prefix_match_result = _compute_prefix_match_strength(
        features.query, features.result, features.official_title
    )
    prefix_match_strength = prefix_match_result[0]
    is_secondary_match = prefix_match_result[1]

    content_type = features.content_type
    if content_type == "unknown" and _detect_category_not_title(features.official_title):
        content_type = "category"
    # Handle category results
    is_category = _detect_category_result(features.result, features.query)
    if is_category and content_type == "unknown":
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
    if _detect_sequel_penalty(features.result, features.query, features.official_title):
        sequel_penalty = float(config.get("sequel_penalty", 0.0))
        score = max(0.0, score - sequel_penalty)

    return score, {
        "match_strength": match_strength,
        "prefix_match_strength": prefix_match_strength,
        "is_secondary_match": is_secondary_match,
        "popularity": popularity,
        "alt_best_popularity": alt_best_popularity,
        "dominance_ratio": dominance_ratio,
        "sequel_penalty": sequel_penalty,
        "best_alternative": best_alt,
        "content_type_computed": content_type,
        "is_category": is_category,
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

    # Detect non-title format BEFORE validation gate
    # This triggers "Unacceptable: Extra Language" for conversational/question results
    # But category results (genre/type descriptions) are valid, not extra language
    is_category_result = _detect_category_result(features.result, features.query)
    non_title_format = _is_non_title_format(features.result) and not is_category_result
    if non_title_format:
        reason = "non-title format (conversational or question)"
        comment = _comment_for_rating(mode, "Unacceptable: Extra Language", 0.0, reason)
        return ScoreOutput(
            task_id=features.task_id,
            rating="Unacceptable: Extra Language",
            comment=comment,
            debug={
                "mode": mode,
                "gates": {"concerns": False, "validation": False, "spelling": False, "extra_language": True},
                "features": features.model_dump(),
                "score": 0.0,
                "thresholds": thresholds,
                "evidence_refs": features.evidence_refs,
            },
        )

    # For category-like results, treat as valid if result is a sensible category phrase
    # even without a specific IMDb title page
    is_category_result = _detect_category_result(features.result, features.query)

    validation_failure = False
    if not features.result.strip():
        validation_failure = True
    has_fallback_validation = bool(features.official_title and features.content_type != "unknown")
    # Allow category results to bypass strict validation
    if not (features.result_imdb_ok or features.result_google_ok) and not has_fallback_validation:
        if not is_category_result:
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

    spelling_gate, incomplete_title, conversational, _ = _detect_spelling_gate(
        features.result, features.official_title, is_category=is_category_result
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

    score, components = _score_features(features, config, mode)
    rating = _map_label(score, thresholds)

    # Get prefix match strength (0-2 scale) and secondary match flag
    prefix_match = components.get("prefix_match_strength", 0)
    is_secondary_match = components.get("is_secondary_match", False)
    is_category = components.get("is_category", False)

    incomplete_cfg = config.get("incomplete_title", {})
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

    # For prefix mode, use prefix_match_strength as primary signal
    content_type_computed = components.get("content_type_computed", features.content_type)
    short_prefix_cap = False  # Will be set in prefix mode if query is too short

    if mode == "prefix":
        # Perfect: strong match (2) AND high match_strength, without major alternatives
        # Good: strong match (2) but weaker position, OR related match (1) with high popularity
        # Acceptable: related match (1), OR niche/incomplete

        # Handle person pages specially
        if content_type_computed == "person":
            # Person pages: score based on name match AND prominence
            # Note: movie alternatives are NOT considered superior to person results
            # because they're different content types
            if prefix_match == 2 and components["match_strength"] >= 0.95:
                # Strong name match - check if this person is among the top candidates
                # If they're not in query_candidates at all, they're not the most obvious choice
                result_lower = features.result.strip().casefold()
                in_top_candidates = False
                for candidate in features.query_candidates[:5]:
                    if result_lower in candidate.casefold() or candidate.casefold() in result_lower:
                        in_top_candidates = True
                        break

                if in_top_candidates:
                    rating = "Perfect"  # This person is among the top completions
                else:
                    rating = "Acceptable"  # Valid but not the most obvious choice
            elif prefix_match == 2:
                # Good match but not exact
                rating = "Good"
            elif prefix_match == 1:
                # Related but not strong match
                rating = "Acceptable"
            else:
                rating = "Unacceptable: Other"

        # Handle category results
        elif is_category:
            # Category results: check if query is well represented
            result_lower = features.result.strip().casefold()
            query_lower = features.query.strip().casefold()
            # Check if query prefix appears prominently
            words = re.findall(r"[a-z0-9]+", result_lower)
            prefix_in_result = any(w.startswith(query_lower) for w in words)
            if prefix_in_result:
                # Check if this is a specific vs broad category
                # Specific: "disney+ animation", "netflix originals"
                # Broad: "action movies that feature superheroes", "movies that..."
                is_broad = ("movies that" in result_lower or "films that" in result_lower
                            or "that feature" in result_lower or len(result_lower.split()) > 4)

                if is_broad:
                    rating = "Good"  # Valid but broad/complex category
                else:
                    # Check if this is a mainstream category
                    mainstream_indicators = ["disney", "netflix", "animation"]
                    is_mainstream = any(ind in result_lower for ind in mainstream_indicators)
                    if is_mainstream:
                        rating = "Perfect"  # Specific mainstream category
                    else:
                        rating = "Good"  # Valid but less mainstream category
            else:
                rating = "Acceptable"  # Category but weak prefix match

        # Handle regular titles
        elif prefix_match == 2:
            # Strong prefix match - check popularity for final rating
            if components["match_strength"] >= 0.95 and components["popularity"] >= 0.7:
                # High popularity and perfect match - but still check for better alternatives
                # Use higher threshold for high-quality content (rating >= 7.0)
                # High-quality content is more defensible even with popular alternatives
                quality_rating = features.imdb_rating or 0
                alt_threshold = 1.25 if quality_rating >= 7.0 else 1.15
                if components["alt_best_popularity"] > components["popularity"] * alt_threshold:
                    rating = "Good"  # Better alternatives exist
                else:
                    rating = "Perfect"
            elif components["match_strength"] >= 0.95 and components["popularity"] >= 0.5:
                # Good popularity and perfect match
                if alternative_exists and components["alt_best_popularity"] > components["popularity"] * 1.2:
                    rating = "Good"  # Better alternatives exist
                else:
                    rating = "Perfect"
            elif alternative_exists:
                rating = "Good"  # Strong match but alternatives exist
            else:
                rating = "Good"  # Strong match but lower popularity

        elif prefix_match == 1:
            # REL03: Secondary/middle-string matches → max Acceptable (not relevant)
            # Example: "dark" matching "The Dark Knight" in middle → Acceptable
            if is_secondary_match:
                # Middle-string matches are poorly related, max Acceptable
                rating = "Acceptable"
            elif components["popularity"] >= 0.7:
                # Related match (not secondary) with high popularity
                rating = "Good"
            else:
                rating = "Acceptable"

        else:
            # Irrelevant match (0)
            rating = "Unacceptable: Other"

        # Niche downgrade: if popularity is very low, cap at Acceptable
        # Note: person pages and categories don't have traditional popularity scores
        if components["popularity"] < 0.2 and rating in ("Perfect", "Good"):
            if not is_category and content_type_computed != "person":
                rating = "Acceptable"

        # R04, POP02, POP03: Prefix-length weighting
        # Short prefixes have many possible intents → cap at Good
        # Long prefixes have fewer intents → can achieve Perfect more easily
        query_len = len(features.query.strip()) if features.query else 0
        short_prefix_threshold = config.get("short_prefix_max_len", 2)
        short_prefix_cap = query_len <= short_prefix_threshold and rating == "Perfect"
        if short_prefix_cap:
            rating = "Good"  # Too many possible intents for short prefix

        # Alternative-based downgrade for non-person, non-category results
        if not is_category and content_type_computed != "person":
            if alternative_exists and components["popularity"] < 0.6 and rating == "Good":
                rating = "Acceptable"

        # Incomplete title handling - ensure at least Acceptable
        if incomplete_title:
            if rating == "Unacceptable: Other":
                rating = "Acceptable"
            # Can upgrade incomplete title if dominance is very high
            upgrade = (
                components["dominance_ratio"] >= incomplete_cfg.get("upgrade_dominance", 0.85)
                and components["match_strength"] >= incomplete_cfg.get("upgrade_match", 0.9)
            )
            if not upgrade and rating in ("Perfect", "Good"):
                rating = "Acceptable"

    else:
        # Intent mode - original logic
        if incomplete_title:
            upgrade = (
                components["dominance_ratio"] >= incomplete_cfg.get("upgrade_dominance", 0.85)
                and components["match_strength"] >= incomplete_cfg.get("upgrade_match", 0.9)
            )
            if not upgrade:
                rating = "Acceptable"

        if dominance_valid:
            if components["dominance_ratio"] < dom_acceptable:
                rating = "Unacceptable: Other"
            else:
                if rating == "Perfect" and components["dominance_ratio"] < dom_perfect:
                    rating = "Good"
                elif rating in ("Perfect", "Good") and components["dominance_ratio"] < dom_good:
                    rating = "Acceptable"

    # JP01-JP06: Japan-specific writing system rules
    jp_writing_mismatch, jp_mismatch_type = _detect_jp_writing_mismatch(
        features.result, features.official_title
    )
    jp_number_mismatch = _detect_jp_number_format_mismatch(
        features.result, features.official_title
    )

    # JP05: Wrong writing system → max Acceptable
    if jp_writing_mismatch and rating in ("Perfect", "Good"):
        rating = "Acceptable"

    # JP06: Alternative number format → max Good (not Perfect)
    if jp_number_mismatch and rating == "Perfect":
        rating = "Good"

    niche_popularity = float(config.get("niche_popularity", 0.2))
    irrelevant_match = float(config.get("irrelevant_match_max", 0.6))
    category_not_title = _detect_category_not_title(features.official_title)
    niche = components["popularity"] < niche_popularity
    irrelevant = components["match_strength"] < irrelevant_match
    weak_prefix_cfg = config.get("weak_prefix", {})
    weak_prefix_max_len = int(weak_prefix_cfg.get("max_len", 2))
    weak_prefix_match_min = float(weak_prefix_cfg.get("match_min", 0.8))
    weak_prefix_pop_min = float(weak_prefix_cfg.get("popularity_min", 0.2))
    unpopular_cfg = config.get("unpopular_acceptance", {})
    unpopular_match_min = float(unpopular_cfg.get("match_min", 0.9))
    unpopular_votes_max = unpopular_cfg.get("votes_max", 5000)
    weak_prefix_match = _weak_prefix_word_match(
        features.query,
        features.official_title,
        weak_prefix_max_len,
    )
    weak_prefix_upgrade = False
    if mode == "prefix" and rating == "Unacceptable: Other" and weak_prefix_match:
        if components["popularity"] >= weak_prefix_pop_min and components["match_strength"] >= weak_prefix_match_min:
            rating = "Acceptable"
            weak_prefix_upgrade = True
    unpopular_upgrade = False
    if mode == "prefix" and rating == "Unacceptable: Other":
        if features.imdb_votes is not None and unpopular_votes_max is not None:
            if components["match_strength"] >= unpopular_match_min and features.imdb_votes < int(unpopular_votes_max):
                rating = "Acceptable"
                unpopular_upgrade = True

    # Complex hint cap: multi-aspect hints max at Good, never Perfect (CH01, CH02)
    is_complex = _is_complex_hint(features.result)
    if is_complex and rating == "Perfect":
        rating = "Good"

    reason_order = [
        ("JP writing system mismatch", jp_writing_mismatch),
        ("JP number format", jp_number_mismatch),
        ("short prefix", short_prefix_cap),
        ("complex hint", is_complex),
        ("incomplete", incomplete_title),
        ("alternative exists", alternative_exists),
        ("niche", niche),
        ("sequel", components["sequel_penalty"] > 0.0),
        ("category-not-title", category_not_title),
        ("irrelevant", irrelevant),
    ]
    downgrade_reason = None
    if rating != "Perfect":
        if weak_prefix_upgrade:
            downgrade_reason = "poorly related"
        elif unpopular_upgrade:
            downgrade_reason = "niche"
        else:
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
                "weak_prefix_word_match": weak_prefix_match,
                "weak_prefix_upgrade": weak_prefix_upgrade,
                "unpopular_upgrade": unpopular_upgrade,
                "is_complex_hint": is_complex,
                "short_prefix_cap": short_prefix_cap,
                "jp_writing_mismatch": jp_writing_mismatch,
                "jp_mismatch_type": jp_mismatch_type,
                "jp_number_mismatch": jp_number_mismatch,
            },
            "score": score,
            "thresholds": thresholds,
            "evidence_refs": features.evidence_refs,
        },
    )
