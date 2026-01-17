"""
IMDb Evidence Collector

Uses requests + BeautifulSoup to extract only needed fields from IMDb pages.
Avoids loading full HTML into LLM context by extracting at collection time.

Usage:
    collector = IMDbEvidenceCollector()
    evidence = collector.collect_from_search("disney movie featuring a blue macaw")
    title_info = collector.get_title_details("tt1436562")
"""

import re
import json
import hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup


@dataclass
class TitleEvidence:
    """Extracted evidence for an IMDb title."""
    imdb_id: str
    official_title: str
    year: Optional[int]
    content_type: str  # movie, series, short, episode, video_game, unknown
    imdb_rating: Optional[float]
    imdb_votes: Optional[int]
    imdb_url: str


@dataclass
class PersonEvidence:
    """Extracted evidence for an IMDb person."""
    imdb_id: str
    name: str
    known_for: Optional[str]
    starmeter: Optional[int]
    imdb_url: str


@dataclass
class SearchEvidence:
    """Evidence from an IMDb search."""
    query: str
    titles: list[TitleEvidence]
    people: list[PersonEvidence]
    notes: Optional[str]


class IMDbEvidenceCollector:
    """Collects evidence from IMDb using requests + BeautifulSoup."""

    BASE_URL = "https://www.imdb.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached(self, url: str) -> Optional[dict]:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / f"{self._cache_key(url)}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())
        return None

    def _set_cached(self, url: str, data: dict):
        if self.cache_dir:
            cache_file = self.cache_dir / f"{self._cache_key(url)}.json"
            cache_file.write_text(json.dumps(data))

    def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            return None

    def _parse_votes(self, votes_str: str) -> Optional[int]:
        """Parse vote count like '269K' or '1.2M' to integer."""
        if not votes_str:
            return None
        votes_str = votes_str.strip().upper()
        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
        for suffix, mult in multipliers.items():
            if suffix in votes_str:
                try:
                    return int(float(votes_str.replace(suffix, "")) * mult)
                except ValueError:
                    return None
        try:
            return int(votes_str.replace(",", ""))
        except ValueError:
            return None

    def _detect_content_type(self, soup: BeautifulSoup, url: str) -> str:
        """Detect content type from page elements."""
        # Check URL pattern
        if "/name/" in url:
            return "person"

        # Look for type indicators in metadata
        meta = soup.find("meta", {"property": "og:type"})
        if meta:
            og_type = meta.get("content", "").lower()
            if "tv_show" in og_type or "series" in og_type:
                return "series"
            if "movie" in og_type or "film" in og_type:
                return "movie"

        # Check for episode indicators
        page_text = soup.get_text().lower()
        if "tv episode" in page_text:
            return "episode"
        if "tv series" in page_text or "tv mini series" in page_text:
            return "series"
        if "short" in page_text[:500]:
            return "short"
        if "video game" in page_text:
            return "video_game"

        return "movie"  # Default assumption

    def get_title_details(self, imdb_id: str) -> Optional[TitleEvidence]:
        """
        Get details for a specific IMDb title.

        Args:
            imdb_id: IMDb ID like 'tt1436562'

        Returns:
            TitleEvidence with extracted fields, or None if failed
        """
        url = f"{self.BASE_URL}/title/{imdb_id}/"

        # Check cache first
        cached = self._get_cached(url)
        if cached:
            return TitleEvidence(**cached)

        html = self._fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_elem = soup.find("h1")
        official_title = title_elem.get_text(strip=True) if title_elem else None

        # Extract year from various possible locations
        year = None
        year_link = soup.find("a", href=re.compile(r"/title/.*/releaseinfo"))
        if year_link:
            year_match = re.search(r"(\d{4})", year_link.get_text())
            if year_match:
                year = int(year_match.group(1))

        # Extract rating and votes from JSON-LD (most reliable)
        rating = None
        votes = None
        script_ld = soup.find("script", {"type": "application/ld+json"})
        if script_ld:
            try:
                ld_data = json.loads(script_ld.string)
                if "aggregateRating" in ld_data:
                    rating = float(ld_data["aggregateRating"].get("ratingValue", 0))
                    votes_raw = ld_data["aggregateRating"].get("ratingCount")
                    if votes_raw:
                        votes = int(votes_raw)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

        # Fallback: extract rating from DOM
        if not rating:
            rating_elem = soup.find("span", class_=re.compile(r"rating"))
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))

        content_type = self._detect_content_type(soup, url)

        evidence = TitleEvidence(
            imdb_id=imdb_id,
            official_title=official_title,
            year=year,
            content_type=content_type,
            imdb_rating=rating,
            imdb_votes=votes,
            imdb_url=url,
        )

        # Cache the result
        self._set_cached(url, asdict(evidence))

        return evidence

    def search(self, query: str, max_results: int = 5) -> SearchEvidence:
        """
        Search IMDb and extract evidence from results.

        Args:
            query: Search query
            max_results: Maximum results per category

        Returns:
            SearchEvidence with titles and people found
        """
        from urllib.parse import quote_plus

        url = f"{self.BASE_URL}/find/?q={quote_plus(query)}"

        html = self._fetch_html(url)
        if not html:
            return SearchEvidence(query=query, titles=[], people=[], notes="Failed to fetch search results")

        soup = BeautifulSoup(html, "html.parser")

        titles = []
        people = []
        seen_title_ids = set()
        seen_person_ids = set()

        # IMDb search results are in list items with links
        # Find all title links - use broader pattern
        title_links = soup.find_all("a", href=re.compile(r"/title/tt\d+"))
        for link in title_links:
            href = link.get("href", "")
            match = re.search(r"(tt\d+)", href)
            if not match:
                continue
            imdb_id = match.group(1)

            # Get title text - look for heading inside or use link text
            title_text = ""
            heading = link.find(["h3", "h4", "span"])
            if heading:
                title_text = heading.get_text(strip=True)
            if not title_text:
                title_text = link.get_text(strip=True)

            # Skip empty links (image-only links)
            if not title_text or len(title_text) < 2:
                continue

            # Now check for duplicates (after we know we have valid text)
            if imdb_id in seen_title_ids:
                continue
            seen_title_ids.add(imdb_id)

            # Find parent container for additional info
            container = link.find_parent("li") or link.find_parent("div", class_=True)
            year = None
            rating = None
            votes = None
            content_type = "unknown"

            if container:
                text = container.get_text(" ", strip=True)
                # Year: look for 4-digit year
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
                if year_match:
                    year = int(year_match.group(1))
                # Rating: look for X.X pattern followed by rating indicators
                rating_match = re.search(r'"?(\d+\.?\d?)"?\s*/?\s*10', text)
                if rating_match:
                    rating = float(rating_match.group(1))
                # Votes: look for numbers with K/M/B suffix in parentheses
                votes_match = re.search(r"\((\d+\.?\d*[KMB])\)", text, re.I)
                if votes_match:
                    votes = self._parse_votes(votes_match.group(1))
                # Content type detection
                text_lower = text.lower()
                if "tv series" in text_lower or "tv-" in text_lower:
                    content_type = "series"
                elif "tv movie" in text_lower:
                    content_type = "tv_movie"
                elif "short" in text_lower:
                    content_type = "short"
                elif "video game" in text_lower:
                    content_type = "video_game"
                elif "tv episode" in text_lower:
                    content_type = "episode"

            titles.append(TitleEvidence(
                imdb_id=imdb_id,
                official_title=title_text,
                year=year,
                content_type=content_type,
                imdb_rating=rating,
                imdb_votes=votes,
                imdb_url=f"{self.BASE_URL}/title/{imdb_id}/",
            ))

            if len(titles) >= max_results:
                break

        # Find people links - use broader pattern
        person_links = soup.find_all("a", href=re.compile(r"/name/nm\d+"))
        for link in person_links:
            href = link.get("href", "")
            match = re.search(r"(nm\d+)", href)
            if not match:
                continue
            imdb_id = match.group(1)

            # Get name
            name = ""
            heading = link.find(["h3", "h4", "span"])
            if heading:
                name = heading.get_text(strip=True)
            if not name:
                name = link.get_text(strip=True)

            # Skip empty links
            if not name or len(name) < 2:
                continue

            # Check duplicates after confirming valid name
            if imdb_id in seen_person_ids:
                continue
            seen_person_ids.add(imdb_id)

            # Find known_for from nearby title links
            known_for = None
            container = link.find_parent("li") or link.find_parent("div", class_=True)
            if container:
                kf_link = container.find("a", href=re.compile(r"/title/tt\d+"))
                if kf_link:
                    known_for = kf_link.get_text(strip=True)

            people.append(PersonEvidence(
                imdb_id=imdb_id,
                name=name,
                known_for=known_for,
                starmeter=None,
                imdb_url=f"{self.BASE_URL}/name/{imdb_id}/",
            ))

            if len(people) >= max_results:
                break

        return SearchEvidence(
            query=query,
            titles=titles,
            people=people,
            notes=None,
        )

    def collect_evidence_for_task(
        self,
        query: str,
        result: str,
        query_imdb_url: Optional[str] = None,
        result_imdb_url: Optional[str] = None,
    ) -> dict:
        """
        Collect all evidence needed for a media hint scoring task.

        Args:
            query: The original query
            result: The claimed result/answer
            query_imdb_url: Direct IMDb URL for query (optional)
            result_imdb_url: Direct IMDb URL for result (optional)

        Returns:
            Dict with evidence ready for scoring
        """
        evidence = {
            "query": query,
            "result": result,
            "query_candidates": [],
            "result_evidence": None,
            "best_alternative": None,
            "notes": None,
        }

        # Search for query candidates
        query_search = self.search(query)
        for title in query_search.titles:
            evidence["query_candidates"].append(asdict(title))
        for person in query_search.people:
            evidence["query_candidates"].append(asdict(person))

        # Search for result
        result_search = self.search(result)
        if result_search.titles:
            top_result = result_search.titles[0]
            # Get full details for top result
            details = self.get_title_details(top_result.imdb_id)
            if details:
                evidence["result_evidence"] = asdict(details)
            else:
                evidence["result_evidence"] = asdict(top_result)
        elif result_search.people:
            evidence["result_evidence"] = asdict(result_search.people[0])

        # Identify best alternative if different from result
        if query_search.titles and evidence["result_evidence"]:
            for title in query_search.titles:
                result_title = evidence["result_evidence"].get("official_title", "").lower()
                if title.official_title.lower() != result_title:
                    details = self.get_title_details(title.imdb_id)
                    if details:
                        evidence["best_alternative"] = asdict(details)
                    else:
                        evidence["best_alternative"] = asdict(title)
                    break

        return evidence


def collect_media_evidence(task: dict) -> dict:
    """
    Convenience function to collect evidence for a media hint task.

    Args:
        task: Dict with 'query', 'result', and optional link fields

    Returns:
        Complete evidence dict ready for scoring
    """
    collector = IMDbEvidenceCollector(
        cache_dir=Path.home() / ".cache" / "imdb_evidence"
    )

    return collector.collect_evidence_for_task(
        query=task.get("query", ""),
        result=task.get("result", ""),
        query_imdb_url=task.get("query_links", {}).get("imdb"),
        result_imdb_url=task.get("result_links", {}).get("imdb"),
    )


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "disney movie featuring a blue macaw"

    collector = IMDbEvidenceCollector()
    evidence = collector.search(query)

    print(f"Search: {query}")
    print(f"Titles found: {len(evidence.titles)}")
    for t in evidence.titles:
        print(f"  - {t.official_title} ({t.year}) [{t.content_type}] {t.imdb_rating}")

    print(f"People found: {len(evidence.people)}")
    for p in evidence.people:
        print(f"  - {p.name} (known for: {p.known_for})")
