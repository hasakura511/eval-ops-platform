"""Lookup decision gate and web search logic."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class LookupDecision:
    """Result of lookup gate evaluation."""
    should_lookup: bool
    reason: str
    query: Optional[str] = None


def needs_lookup(
    query: str,
    query_type: str,
    result_title: str,
    result_type: str,
    result_genre: Optional[str] = None,
    result_year: Optional[str] = None,
    disambiguation: Optional[str] = None,
) -> LookupDecision:
    """
    Determine if web lookup is needed for this question.

    Returns (should_lookup, reason_or_query).

    MUST LOOKUP when ANY of:
    1. Platform query (e.g., "on hulu") — verify availability
    2. Episode count query — verify exact count
    3. Director/creator query — verify attribution
    4. Popularity ambiguous (older title, unknown studio)
    5. Genre mismatch between query and metadata
    6. Similarity query — verify director/studio connections
    7. Time-period query where result might be SET in different era than RELEASED

    SKIP LOOKUP when ALL of:
    1. Format mismatch obvious (Movie vs Show)
    2. Time period mismatch clear from release year
    3. Result type mismatch (Person card when movie expected — except actor queries)
    4. Navigational target clearly different from result
    """
    query_lower = query.lower()

    # === ALWAYS LOOKUP patterns ===

    # Platform availability queries
    platforms = ["hulu", "netflix", "apple tv+", "disney+", "amazon prime",
                 "peacock", "paramount+", "hbo max", "on apple"]
    for platform in platforms:
        if platform in query_lower:
            return LookupDecision(
                should_lookup=True,
                reason="Platform availability query",
                query=f"{result_title} streaming availability {platform}"
            )

    # Episode count queries
    episode_patterns = [
        r"episodes?\s+per\s+season",
        r"more\s+than\s+\d+\s+episodes?",
        r"how\s+many\s+episodes?",
        r"\d+\s+episodes?\s+per",
    ]
    for pattern in episode_patterns:
        if re.search(pattern, query_lower):
            return LookupDecision(
                should_lookup=True,
                reason="Episode count query",
                query=f"{result_title} episodes per season count"
            )

    # Director/creator queries
    director_patterns = [
        r"director\s+of",
        r"by\s+the\s+director",
        r"directed\s+by",
        r"from\s+the\s+director",
        r"creator\s+of",
        r"created\s+by",
    ]
    for pattern in director_patterns:
        if re.search(pattern, query_lower):
            return LookupDecision(
                should_lookup=True,
                reason="Director/creator query",
                query=f"{result_title} director creator"
            )

    # Similarity queries ALWAYS need lookup for connections
    if query_type == "Similarity":
        # Extract the reference content from query
        match = re.search(r"(?:like|similar to|movies like|shows like)\s+(.+?)(?:\s*$|\s+and|\s+or)", query_lower)
        seed_title = match.group(1) if match else "referenced content"
        return LookupDecision(
            should_lookup=True,
            reason="Similarity query - verify connections",
            query=f"{result_title} vs {seed_title} director studio cast comparison"
        )

    # Time period queries - check if SET in different era than RELEASED
    time_period_patterns = [
        (r"(\d{4})s", lambda m: (int(m.group(1)), int(m.group(1)) + 9)),  # 1980s
        (r"(\d{2})s\b", lambda m: _expand_decade(m.group(1))),  # 80s
        (r"from\s+the\s+(\d{4})s", lambda m: (int(m.group(1)), int(m.group(1)) + 9)),
        (r"from\s+the\s+(\d{2})s\b", lambda m: _expand_decade(m.group(1))),
    ]

    for pattern, extractor in time_period_patterns:
        match = re.search(pattern, query_lower)
        if match:
            try:
                decade_start, decade_end = extractor(match)
                if result_year:
                    release_year = int(result_year)
                    # If release year is outside queried decade, might still be SET in that era
                    if not (decade_start <= release_year <= decade_end):
                        return LookupDecision(
                            should_lookup=True,
                            reason="Time period query - verify when content is SET vs RELEASED",
                            query=f"{result_title} {result_year} what year decade is it set in"
                        )
            except (ValueError, TypeError):
                pass

    # Genre mismatch between query and metadata
    genre_keywords = {
        "romance": ["romance", "romantic", "love story"],
        "comedy": ["comedy", "funny", "comedic", "humor"],
        "action": ["action", "thriller", "adventure"],
        "horror": ["horror", "scary", "thriller"],
        "drama": ["drama", "dramatic"],
        "documentary": ["documentary", "doc", "docuseries"],
        "animation": ["animated", "animation", "cartoon"],
        "sci-fi": ["sci-fi", "science fiction", "scifi", "futuristic"],
        "fantasy": ["fantasy", "magical"],
    }

    query_genre = None
    for genre, keywords in genre_keywords.items():
        for kw in keywords:
            if kw in query_lower:
                query_genre = genre
                break
        if query_genre:
            break

    if query_genre and result_genre:
        result_genre_lower = result_genre.lower()
        # Check if there's a potential mismatch
        genre_matches = any(kw in result_genre_lower for kw in genre_keywords.get(query_genre, []))
        if not genre_matches and query_genre != result_genre_lower:
            return LookupDecision(
                should_lookup=True,
                reason=f"Potential genre mismatch: query implies {query_genre}, metadata shows {result_genre}",
                query=f"{result_title} genre {query_genre}"
            )

    # === SKIP LOOKUP patterns ===

    # Format mismatch obvious
    if "movie" in query_lower and result_type == "Show":
        return LookupDecision(
            should_lookup=False,
            reason="Format mismatch obvious: query wants Movie, result is Show"
        )

    if ("show" in query_lower or "series" in query_lower) and result_type == "Movie":
        return LookupDecision(
            should_lookup=False,
            reason="Format mismatch obvious: query wants Show/Series, result is Movie"
        )

    # Navigational target clearly different
    if query_type == "Navigational" and disambiguation:
        # Simple check: if disambiguation title is completely different from result
        disambig_lower = disambiguation.lower()
        result_lower = result_title.lower()
        # Check for shared significant words
        disambig_words = set(re.findall(r'\b\w{4,}\b', disambig_lower))
        result_words = set(re.findall(r'\b\w{4,}\b', result_lower))
        overlap = disambig_words & result_words
        if not overlap:
            # No overlap - but might still share attributes, so lookup to verify
            return LookupDecision(
                should_lookup=True,
                reason="Navigational miss - verify shared attributes",
                query=f"{result_title} {disambiguation} same actor director genre"
            )

    # Default: metadata sufficient
    return LookupDecision(
        should_lookup=False,
        reason="Metadata sufficient for rating"
    )


def _expand_decade(short: str) -> tuple[int, int]:
    """Expand 2-digit decade to full years (e.g., '80' -> (1980, 1989))."""
    decade = int(short)
    if decade >= 20:  # 20-99 -> 1920-1999
        century = 1900
    else:  # 00-19 -> 2000-2019
        century = 2000
    start = century + decade
    return (start, start + 9)
