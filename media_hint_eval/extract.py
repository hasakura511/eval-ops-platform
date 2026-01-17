import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from .schemas import AlternativeCandidate, Features, TaskInput
from .utils import read_jsonl, write_jsonl


IMDB_TYPE_MAP = {
    "movie": "movie",
    "tvseries": "series",
    "tvepisode": "series",
    "tvminiseries": "series",
    "short": "short",
    "person": "person",
}


def _load_meta(task_dir: str, key: str) -> Optional[dict]:
    path = os.path.join(task_dir, f"{key}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_html(task_dir: str, key: str) -> Optional[str]:
    path = os.path.join(task_dir, f"{key}.html")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _parse_json_ld(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "@type" in item:
                    return item
        if isinstance(data, dict) and "@type" in data:
            return data
    return None


def _extract_imdb(html: str, url: Optional[str] = None) -> Dict[str, Optional[object]]:
    data = {
        "official_title": None,
        "content_type": "unknown",
        "imdb_rating": None,
        "imdb_votes": None,
        "starmeter": None,
        "release_year": None,
        "end_year": None,
    }
    if not html:
        return data

    # Detect person page from URL pattern
    is_person_page = False
    if url and "/name/nm" in url:
        is_person_page = True
        data["content_type"] = "person"

    json_ld = _parse_json_ld(html)
    if json_ld:
        raw_type = str(json_ld.get("@type", "")).lower()
        detected_type = IMDB_TYPE_MAP.get(raw_type, "unknown")
        # Only override if not already detected as person from URL
        if not is_person_page:
            data["content_type"] = detected_type
        elif detected_type == "person":
            data["content_type"] = "person"
        name = json_ld.get("name")
        if isinstance(name, str):
            data["official_title"] = name.strip()
        rating = json_ld.get("aggregateRating") or {}
        if isinstance(rating, dict):
            if rating.get("ratingValue") is not None:
                try:
                    data["imdb_rating"] = float(rating.get("ratingValue"))
                except (TypeError, ValueError):
                    pass
            if rating.get("ratingCount") is not None:
                try:
                    data["imdb_votes"] = int(str(rating.get("ratingCount")).replace(",", ""))
                except (TypeError, ValueError):
                    pass
        # Extract release year from datePublished (format: "YYYY-MM-DD" or "YYYY")
        date_published = json_ld.get("datePublished")
        if date_published and isinstance(date_published, str):
            year_match = re.match(r"(\d{4})", date_published)
            if year_match:
                try:
                    data["release_year"] = int(year_match.group(1))
                except ValueError:
                    pass

    soup = BeautifulSoup(html, "html.parser")

    # Extract year range from title or HTML (e.g., "2019-2023" or "2019-")
    # This handles series with end dates
    year_range_match = re.search(r"\((\d{4})(?:[–\-](\d{4})?)?(?:\s*\))|\b(\d{4})[–\-](\d{4})?\b", html[:5000])
    if year_range_match:
        groups = year_range_match.groups()
        start_year = groups[0] or groups[2]
        end_year = groups[1] or groups[3]
        if start_year and data["release_year"] is None:
            try:
                data["release_year"] = int(start_year)
            except ValueError:
                pass
        if end_year:
            try:
                data["end_year"] = int(end_year)
            except ValueError:
                pass
    if data["official_title"] is None:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title.get("content").replace(" - IMDb", "").strip()
            if title:
                data["official_title"] = title
    if data["official_title"] is None and soup.title and soup.title.string:
        data["official_title"] = soup.title.string.replace(" - IMDb", "").strip()

    starmeter_match = re.search(r"STARmeter\s*([0-9,]+)", html, re.IGNORECASE)
    if starmeter_match:
        try:
            data["starmeter"] = int(starmeter_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Additional person page detection from HTML structure
    if data["content_type"] == "unknown":
        # Check for person-specific elements
        if soup.find("div", {"data-testid": "hero__pageTitle"}):
            # Check if it's a name page by looking for filmography section
            if soup.find("section", {"data-testid": "Filmography"}):
                data["content_type"] = "person"

    return data


def _extract_google_candidates(html: str, limit: int = 5) -> List[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for header in soup.find_all("h3"):
        text = header.get_text(strip=True)
        if text and text not in candidates:
            candidates.append(text)
        if len(candidates) >= limit:
            break
    return candidates


def _extract_imdb_candidates(html: str, limit: int = 5) -> List[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        if "/title/tt" not in href and "/name/nm" not in href:
            continue
        text = anchor.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        if text not in candidates:
            candidates.append(text)
        if len(candidates) >= limit:
            break
    return candidates


def _extract_google_title(html: str) -> Optional[str]:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return og_title.get("content").strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def _load_task(task_dir: str) -> Optional[TaskInput]:
    path = os.path.join(task_dir, "task.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return TaskInput.model_validate(payload)


def _best_evidence(task_dir: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], List[str]]:
    errors = []
    result_imdb_meta = _load_meta(task_dir, "result_imdb")
    result_google_meta = _load_meta(task_dir, "result_google")
    query_google_meta = _load_meta(task_dir, "query_google")
    query_imdb_meta = _load_meta(task_dir, "query_imdb")

    result_imdb_url = result_imdb_meta.get("final_url") if result_imdb_meta else None
    result_google_url = result_google_meta.get("final_url") if result_google_meta else None
    query_google_url = query_google_meta.get("final_url") if query_google_meta else None
    query_imdb_url = query_imdb_meta.get("final_url") if query_imdb_meta else None

    for meta, name in ((result_imdb_meta, "result_imdb"), (result_google_meta, "result_google"),
                       (query_google_meta, "query_google"), (query_imdb_meta, "query_imdb")):
        if meta:
            if meta.get("error"):
                errors.append(f"{name}: {meta.get('error')}")
            if meta.get("page_status") == "blocked":
                errors.append(f"{name}: blocked")

    return result_imdb_url, result_google_url, query_google_url, query_imdb_url, errors


def _candidate_popularity(candidate: AlternativeCandidate) -> float:
    max_votes = 1000000.0
    rating_weight = 0.4
    votes_weight = 0.6
    starmeter_max = 500000.0

    if candidate.content_type == "person":
        if candidate.starmeter is None:
            return 0.0
        rank = float(candidate.starmeter)
        return max(0.0, 1.0 - min(rank, starmeter_max) / starmeter_max)

    rating_score = 0.0
    if candidate.imdb_rating is not None:
        rating_score = max(0.0, min(float(candidate.imdb_rating) / 10.0, 1.0))

    votes_score = 0.0
    if candidate.imdb_votes is not None and candidate.imdb_votes > 0:
        votes_score = min(1.0, math.log10(candidate.imdb_votes) / math.log10(max_votes))

    return (rating_weight * rating_score) + (votes_weight * votes_score)


def _read_alternative_candidates(task_dir: str) -> List[AlternativeCandidate]:
    alternatives = []
    for idx in range(1, 4):
        key = f"alt_imdb_{idx}"
        html = _load_html(task_dir, key)
        meta = _load_meta(task_dir, key)
        if not html or not meta:
            continue
        alt_url = meta.get("final_url")
        imdb_data = _extract_imdb(html, alt_url)
        candidate = AlternativeCandidate(
            name=imdb_data.get("official_title"),
            content_type=imdb_data.get("content_type") or "unknown",
            imdb_votes=imdb_data.get("imdb_votes"),
            imdb_rating=imdb_data.get("imdb_rating"),
            starmeter=imdb_data.get("starmeter"),
            release_year=imdb_data.get("release_year"),
            end_year=imdb_data.get("end_year"),
            imdb_url=alt_url,
            source=key,
        )
        alternatives.append(candidate)
    return alternatives


def _parse_page_status(meta: Optional[dict], html: Optional[str]) -> Tuple[bool, bool]:
    if not meta:
        return False, False
    if meta.get("page_status") == "blocked":
        return False, True
    if not html:
        return False, False
    return True, False


def extract_task(task_dir: str) -> Optional[Features]:
    task = _load_task(task_dir)
    if not task:
        return None

    result_imdb_html = _load_html(task_dir, "result_imdb")
    result_google_html = _load_html(task_dir, "result_google")
    query_google_html = _load_html(task_dir, "query_google")
    query_imdb_html = _load_html(task_dir, "query_imdb")

    # Get result_imdb URL for person page detection
    result_imdb_meta = _load_meta(task_dir, "result_imdb")
    result_imdb_url = result_imdb_meta.get("final_url") if result_imdb_meta else None

    imdb_data = _extract_imdb(result_imdb_html, result_imdb_url) if result_imdb_html else {}
    google_title = _extract_google_title(result_google_html)

    official_title = imdb_data.get("official_title")
    content_type = imdb_data.get("content_type") or "unknown"
    if not official_title and google_title:
        official_title = google_title

    query_candidates = _extract_imdb_candidates(query_imdb_html)
    if not query_candidates:
        query_candidates = _extract_google_candidates(query_google_html)
    if not query_candidates:
        query_candidates = _extract_google_candidates(query_imdb_html)

    result_imdb_url_from_evidence, result_google_url, query_google_url, query_imdb_url, errors = _best_evidence(task_dir)
    alternatives = _read_alternative_candidates(task_dir)
    best_alternative = None
    if alternatives:
        best_alternative = max(alternatives, key=_candidate_popularity)

    # result_imdb_meta already loaded above
    result_google_meta = _load_meta(task_dir, "result_google")
    result_imdb_ok, result_imdb_blocked = _parse_page_status(result_imdb_meta, result_imdb_html)
    result_google_ok, result_google_blocked = _parse_page_status(result_google_meta, result_google_html)
    # For person pages, having a title and content_type is enough
    # For title pages, we need the full parsed data
    imdb_parsed = bool(imdb_data.get("official_title")) and content_type != "unknown"
    google_parsed = bool(google_title)
    result_imdb_ok = result_imdb_ok and imdb_parsed
    result_google_ok = result_google_ok and google_parsed

    features = Features(
        task_id=task.task_id,
        query=task.query,
        result=task.result,
        official_title=official_title,
        content_type=content_type,
        imdb_votes=imdb_data.get("imdb_votes"),
        imdb_rating=imdb_data.get("imdb_rating"),
        starmeter=imdb_data.get("starmeter"),
        release_year=imdb_data.get("release_year"),
        end_year=imdb_data.get("end_year"),
        query_candidates=query_candidates,
        alternatives=alternatives,
        best_alternative=best_alternative,
        result_imdb_ok=result_imdb_ok,
        result_google_ok=result_google_ok,
        result_imdb_blocked=result_imdb_blocked,
        result_google_blocked=result_google_blocked,
        evidence_refs={
            "result_imdb_url": result_imdb_url or result_imdb_url_from_evidence,
            "result_google_url": result_google_url,
            "query_google_url": query_google_url,
            "query_imdb_url": query_imdb_url,
        },
        errors=errors,
    )
    return features


def extract_cache(cache_dir: str, out_path: str) -> None:
    features_rows = []
    for entry in sorted(os.listdir(cache_dir)):
        task_dir = os.path.join(cache_dir, entry)
        if not os.path.isdir(task_dir):
            continue
        features = extract_task(task_dir)
        if features:
            features_rows.append(features.model_dump())
    write_jsonl(out_path, features_rows)
