"""Rating logic for Video Complex Queries."""

import re
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class RatingResult:
    """Result of rating evaluation."""
    rating: str
    reasoning: str
    lookup_performed: bool = False
    lookup_query: Optional[str] = None


VALID_RATINGS = ["Perfect", "Excellent", "Good", "Acceptable", "Off-Topic", "Problem"]


def rate_browse(
    query: str,
    result_title: str,
    result_type: str,
    result_genre: Optional[str],
    result_year: Optional[str],
    is_relevant: bool,
    is_popular: bool,
    is_recent: bool,
    is_time_period_query: bool = False,
    is_kids_content: bool = False,
    is_kids_query: bool = False,
    lookup_info: Optional[str] = None,
) -> str:
    """
    Rate Browse query results.

    No Perfect for Browse - ceiling is Excellent.

    Rating matrix:
    - Relevant + Popular + Recent = Excellent
    - Relevant + Popular OR Recent = Good
    - Relevant only = Acceptable
    - Not relevant = Off-Topic

    Time-period queries waive recency requirement.
    Kids content demoted by 1 unless kids query.
    """
    if not is_relevant:
        return "Off-Topic"

    # Time period queries waive recency
    if is_time_period_query:
        is_recent = True  # Waived

    if is_popular and is_recent:
        rating = "Excellent"
    elif is_popular or is_recent:
        rating = "Good"
    else:
        rating = "Acceptable"

    # Kids content demotion (but never below Acceptable)
    if is_kids_content and not is_kids_query and rating != "Acceptable":
        demotion = {
            "Excellent": "Good",
            "Good": "Acceptable",
        }
        rating = demotion.get(rating, rating)

    return rating


def rate_similarity(
    query: str,
    result_title: str,
    seed_title: str,
    target_audience_match: bool,
    factual_match: bool,
    theme_match: bool,
    lookup_info: Optional[str] = None,
) -> str:
    """
    Rate Similarity query results.

    No Perfect for Similarity - ceiling is Excellent.

    Rating matrix:
    - 3/3 categories = Excellent
    - 2/3 categories = Good
    - 1/3 categories = Acceptable
    - 0/3 categories = Off-Topic

    Categories:
    - Target Audience (age rating, demographic)
    - Factual Aspects (studio, director, cast, genre, format)
    - Theme (story themes, tone, message)

    CRITICAL: Theme similarity bar is HIGH.
    Same studio + same director does NOT imply same theme.
    Must verify actual story themes match.
    """
    matches = sum([target_audience_match, factual_match, theme_match])

    if matches == 3:
        return "Excellent"
    elif matches == 2:
        return "Good"
    elif matches == 1:
        return "Acceptable"
    else:
        return "Off-Topic"


def rate_navigational(
    query: str,
    result_title: str,
    disambiguation: Optional[str],
    is_exact_match: bool,
    is_sequel_prequel: bool = False,
    is_bundle: bool = False,
    shared_attributes: int = 0,
    is_person_card: bool = False,
    is_actor_query: bool = False,
    lookup_info: Optional[str] = None,
) -> str:
    """
    Rate Navigational query results.

    Perfect IS allowed for Navigational.

    Rating matrix:
    - Exact match (primary intent) = Perfect
    - Sequel/prequel or bundle = Excellent
    - Secondary intent, popular or recent = Good
    - Poor secondary intent = Acceptable
    - Not relevant = Off-Topic

    CALIBRATION EXCEPTIONS:
    1. Person cards for actor queries = Excellent
       (Person page provides filmography)
    2. Navigational miss with shared attributes = Acceptable
       (same actor + genre + era = Acceptable even when wrong title)
    """
    # Calibration Exception 1: Person cards for actor queries
    if is_person_card and is_actor_query:
        return "Excellent"

    # Exact match = Perfect
    if is_exact_match:
        return "Perfect"

    # Sequel/prequel or bundle = Excellent
    if is_sequel_prequel or is_bundle:
        return "Excellent"

    # Calibration Exception 2: Navigational miss with shared attributes
    # same actor + same genre + same era = Acceptable
    if shared_attributes >= 2:
        return "Acceptable"

    # If we get here with a disambiguation (target) but no match
    if disambiguation and not is_exact_match:
        if shared_attributes >= 1:
            return "Acceptable"
        return "Off-Topic"

    # Default for secondary intent
    return "Good"


def detect_time_period_query(query: str) -> tuple[bool, Optional[tuple[int, int]]]:
    """
    Detect if query is asking for specific time period content.

    Returns (is_time_period_query, (decade_start, decade_end) or None).
    """
    patterns = [
        (r"(\d{4})s\b", lambda m: (int(m.group(1)), int(m.group(1)) + 9)),
        (r"\b(\d{2})s\b", lambda m: _expand_decade(m.group(1))),
        (r"from\s+the\s+(\d{4})s", lambda m: (int(m.group(1)), int(m.group(1)) + 9)),
        (r"from\s+the\s+(\d{2})s\b", lambda m: _expand_decade(m.group(1))),
    ]

    for pattern, extractor in patterns:
        match = re.search(pattern, query.lower())
        if match:
            try:
                return (True, extractor(match))
            except (ValueError, TypeError):
                pass

    return (False, None)


def detect_actor_query(query: str) -> bool:
    """Detect if query is looking for actor's filmography."""
    actor_patterns = [
        r"starring\s+",
        r"movies?\s+with\s+",
        r"shows?\s+with\s+",
        r"films?\s+with\s+",
        r"everything\s+with\s+",
        r"featuring\s+",
    ]
    for pattern in actor_patterns:
        if re.search(pattern, query.lower()):
            return True
    return False


def detect_kids_content(recommended_age: Optional[str], rating: Optional[str]) -> bool:
    """Detect if content is kids-oriented."""
    if recommended_age:
        # Parse age like "7+", "8+", "10+"
        match = re.match(r"(\d+)\+?", recommended_age)
        if match:
            age = int(match.group(1))
            if age <= 10:
                return True

    if rating:
        kids_ratings = ["G", "PG", "TV-Y", "TV-Y7", "TV-G"]
        if rating.upper() in kids_ratings:
            return True

    return False


def detect_kids_query(query: str) -> bool:
    """Detect if query is specifically for kids content."""
    kids_patterns = [
        r"\bkids?\b",
        r"\bchildren\b",
        r"\bfamily\b",
        r"\bfor\s+my\s+kids?\b",
        r"\banimated\b",
        r"\bcartoon\b",
    ]
    for pattern in kids_patterns:
        if re.search(pattern, query.lower()):
            return True
    return False


def generate_reasoning(
    query: str,
    query_type: str,
    result_title: str,
    result_type: str,
    rating: str,
    is_relevant: bool,
    is_popular: bool,
    is_recent: bool,
    lookup_info: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> str:
    """
    Generate single-paragraph reasoning for the rating.

    Format:
    1. "The query is looking for [intent expansion]."
    2. "[Abbreviation] refers to [expansion]." (if applicable)
    3. "[Result title] is/was [evidence matching or not matching]."
    4. "[Rating justification]."

    NO: bullets, numbered lists, Q&A format
    """
    parts = []

    # 1. Query intent
    intent = _expand_intent(query, query_type)
    parts.append(f"The query is looking for {intent}.")

    # 2. Abbreviation expansion (if any)
    abbrev = _detect_abbreviation(query)
    if abbrev:
        parts.append(abbrev)

    # 3. Result connection
    if is_relevant:
        connection = f"{result_title} is a {result_type.lower()}"
        if is_popular and is_recent:
            connection += " that is both popular and recent"
        elif is_popular:
            connection += " that is popular but not recent"
        elif is_recent:
            connection += " that is recent but less well-known"
        else:
            connection += " that, while relevant, is neither particularly popular nor recent"

        if lookup_info:
            connection += f". {lookup_info}"

        parts.append(connection + ".")
    else:
        parts.append(f"{result_title} is not relevant to this query as it does not match the search intent.")

    # 4. Rating justification
    justification = _rating_justification(rating, query_type, is_relevant, is_popular, is_recent)
    if additional_context:
        justification = f"{additional_context} {justification}"
    parts.append(justification)

    return " ".join(parts)


def _expand_intent(query: str, query_type: str) -> str:
    """Expand query into intent description."""
    query_lower = query.lower()

    if query_type == "Navigational":
        return f"a specific piece of content matching '{query}'"
    elif query_type == "Similarity":
        # Extract the reference
        match = re.search(r"(?:like|similar to)\s+(.+?)(?:\s*$|\s+and|\s+or)", query_lower)
        if match:
            ref = match.group(1)
            return f"content similar to {ref}"
        return f"content similar to referenced material"
    else:  # Browse
        return f"content matching the browsing intent: {query}"


def _detect_abbreviation(query: str) -> Optional[str]:
    """Detect and expand common abbreviations in query."""
    abbrevs = {
        r"\b(\d{2})s\b": lambda m: f"The {m.group(1)}s refers to the years {_expand_decade(m.group(1))[0]} to {_expand_decade(m.group(1))[1]}.",
        r"\b(\d{4})s\b": lambda m: f"The {m.group(1)}s refers to the years {int(m.group(1))} to {int(m.group(1)) + 9}.",
        r"\brom-?com\b": lambda _: "Rom-com is an abbreviation for romantic comedy.",
        r"\bsci-?fi\b": lambda _: "Sci-fi is an abbreviation for science fiction.",
        r"\batv\+?\b": lambda _: "ATV+ refers to Apple TV+ streaming service.",
        r"\bdoc\b": lambda _: "Doc is short for documentary.",
    }

    for pattern, expander in abbrevs.items():
        match = re.search(pattern, query.lower())
        if match:
            return expander(match)

    return None


def _rating_justification(
    rating: str,
    query_type: str,
    is_relevant: bool,
    is_popular: bool,
    is_recent: bool,
) -> str:
    """Generate rating justification."""
    justifications = {
        "Perfect": "This is the primary intent of the query, making it a perfect result.",
        "Excellent": "This makes it an excellent result for the query.",
        "Good": "This makes it a good result for the query.",
        "Acceptable": "While relevant, the result is acceptable but not ideal.",
        "Off-Topic": "This result is off-topic as it does not match the query intent.",
        "Problem": "There is a technical issue with this result.",
    }
    return justifications.get(rating, "")


def _expand_decade(short: str) -> tuple[int, int]:
    """Expand 2-digit decade to full years."""
    decade = int(short)
    if decade >= 20:
        century = 1900
    else:
        century = 2000
    start = century + decade
    return (start, start + 9)
