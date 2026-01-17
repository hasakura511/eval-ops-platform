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


def _detect_category_result(result: str, query: str) -> bool:
    """
    Detect if result is a category/genre description rather than a specific title.

    Category results are valid completions like "disney+ animation" for query "ani"
    that describe a genre/category rather than pointing to a specific title.
    """
    if not result:
        return False

    result_lower = result.strip().casefold()
    query_lower = (query or "").strip().casefold()

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
    if _detect_sequel_penalty(features.result, features.query):
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
    # This allows proper "Unacceptable: Spelling" for conversational/question results
    # But category results (genre/type descriptions) are valid, not spelling errors
    is_category_result = _detect_category_result(features.result, features.query)
    non_title_format = _is_non_title_format(features.result) and not is_category_result
    if non_title_format:
        reason = "non-title format (conversational or question)"
        comment = _comment_for_rating(mode, "Unacceptable: Spelling", 0.0, reason)
        return ScoreOutput(
            task_id=features.task_id,
            rating="Unacceptable: Spelling",
            comment=comment,
            debug={
                "mode": mode,
                "gates": {"concerns": False, "validation": False, "spelling": True, "non_title_format": True},
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
            # Secondary word matches - check if user is skipping an article
            if is_secondary_match:
                # Users commonly skip articles (a, an, the) when searching
                # If first word is an article, this is a valid secondary intent → Good
                # Otherwise it's poorly related → Acceptable
                first_word = ""
                if features.official_title:
                    title_words = features.official_title.lower().split()
                    if title_words:
                        first_word = title_words[0]
                articles = {"a", "an", "the"}
                if first_word in articles:
                    rating = "Good"  # Valid secondary intent (article-skipping)
                else:
                    rating = "Acceptable"  # Poorly related
            elif components["popularity"] >= 0.7:
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
            },
            "score": score,
            "thresholds": thresholds,
            "evidence_refs": features.evidence_refs,
        },
    )
