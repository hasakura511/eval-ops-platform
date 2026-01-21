import json
import os
import re
import time
from typing import Dict, Optional, Tuple

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from .schemas import TaskInput
from .utils import ensure_dir, read_jsonl, safe_filename, utc_now_iso


DEFAULT_TIMEOUT_MS = 30000


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def _detect_blocked_page(final_url: Optional[str], html: Optional[str]) -> bool:
    if not final_url or not html:
        return False
    lowered = html.casefold()
    if "consent.google.com" in final_url:
        return True
    blocked_markers = [
        "unusual traffic",
        "detected unusual traffic",
        "sorry/index",
        "recaptcha",
        "before you continue",
        "verify you are not a robot",
        "robot check",
        "captcha",
    ]
    if "google.com" in final_url or "youtube.com" in final_url:
        return any(marker in lowered for marker in blocked_markers)
    return False


def _extract_imdb_candidate_urls(html: str, limit: int = 5) -> Tuple[str, ...]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        match = re.search(r"/(title/tt\\d+|name/nm\\d+)", href)
        if not match:
            continue
        path = match.group(1)
        url = f"https://www.imdb.com/{path}/"
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return tuple(urls)


def _extract_google_imdb_urls(html: str, limit: int = 5) -> Tuple[str, ...]:
    urls = []
    if not html:
        return tuple(urls)
    for match in re.findall(r"https?://www\\.imdb\\.com/(title/tt\\d+|name/nm\\d+)", html):
        url = f"https://www.imdb.com/{match}/"
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return tuple(urls)


def _fetch_url(page, url: str, timeout_ms: int, retries: int) -> Dict[str, Optional[str]]:
    last_error = None
    response = None
    for _ in range(retries + 1):
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(250)
            html = page.content()
            page_status = "blocked" if _detect_blocked_page(page.url, html) else "ok"
            return {
                "html": html,
                "final_url": page.url,
                "status": response.status if response else None,
                "page_status": page_status,
                "error": None,
            }
        except PlaywrightTimeoutError as exc:
            last_error = f"timeout: {exc}"
        except Exception as exc:  # pylint: disable=broad-except
            last_error = f"error: {exc}"
        time.sleep(0.5)
    return {
        "html": None,
        "final_url": page.url if page else None,
        "status": response.status if response else None,
        "page_status": "error",
        "error": last_error,
    }


def _collect_link(page, url: str, meta_path: str, html_path: str, screenshot_path: Optional[str],
                  timeout_ms: int, retries: int) -> None:
    if not url:
        return None
    result = _fetch_url(page, url, timeout_ms=timeout_ms, retries=retries)
    html = result.pop("html")
    if html is not None:
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html)
    if screenshot_path:
        try:
            page.screenshot(path=screenshot_path, full_page=True)
        except Exception:
            pass
    meta = {
        "input_url": url,
        "final_url": result.get("final_url"),
        "status": result.get("status"),
        "page_status": result.get("page_status"),
        "timestamp": utc_now_iso(),
        "error": result.get("error"),
        "html_path": html_path if html is not None else None,
        "screenshot_path": screenshot_path,
    }
    _write_json(meta_path, meta)
    return {"html": html, "meta": meta}


def collect(input_path: str, cache_dir: str, screenshot: bool = False, force: bool = False,
            collect_alternatives: bool = False, timeout_ms: int = DEFAULT_TIMEOUT_MS, retries: int = 2,
            user_agent: Optional[str] = None) -> None:
    tasks_raw = read_jsonl(input_path)
    ensure_dir(cache_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)

        for row in tasks_raw:
            task = TaskInput.model_validate(row)
            task_dir = os.path.join(cache_dir, safe_filename(task.task_id))
            ensure_dir(task_dir)
            task_path = os.path.join(task_dir, "task.json")
            if not os.path.exists(task_path):
                _write_json(task_path, task.model_dump())

            candidate_urls = []
            result_imdb_url = task.result_links.imdb if task.result_links else None

            for prefix, links in (("query", task.query_links), ("result", task.result_links)):
                for key, url in links.model_dump().items():
                    if not url:
                        continue
                    cache_key = f"{prefix}_{key}"
                    meta_path = os.path.join(task_dir, f"{cache_key}.json")
                    html_path = os.path.join(task_dir, f"{cache_key}.html")
                    screenshot_path = os.path.join(task_dir, f"{cache_key}.png") if screenshot else None

                    if not force and os.path.exists(meta_path):
                        if collect_alternatives and prefix == "query":
                            if os.path.exists(html_path):
                                with open(html_path, "r", encoding="utf-8") as handle:
                                    cached_html = handle.read()
                                if key == "imdb" and cached_html:
                                    candidate_urls = list(_extract_imdb_candidate_urls(cached_html, limit=5))
                                elif key == "google" and cached_html and not candidate_urls:
                                    candidate_urls = list(_extract_google_imdb_urls(cached_html, limit=5))
                        continue

                    page = context.new_page()
                    result = _collect_link(
                        page,
                        url,
                        meta_path=meta_path,
                        html_path=html_path,
                        screenshot_path=screenshot_path,
                        timeout_ms=timeout_ms,
                        retries=retries,
                    )
                    page.close()
                    if collect_alternatives and prefix == "query":
                        html = result["html"] if result else None
                        if key == "imdb" and html:
                            candidate_urls = list(_extract_imdb_candidate_urls(html, limit=5))
                        elif key == "google" and html and not candidate_urls:
                            candidate_urls = list(_extract_google_imdb_urls(html, limit=5))

            if collect_alternatives and candidate_urls:
                filtered = []
                for url in candidate_urls:
                    if result_imdb_url and result_imdb_url.rstrip("/") in url.rstrip("/"):
                        continue
                    if url not in filtered:
                        filtered.append(url)
                for idx, url in enumerate(filtered[:3], start=1):
                    cache_key = f"alt_imdb_{idx}"
                    meta_path = os.path.join(task_dir, f"{cache_key}.json")
                    html_path = os.path.join(task_dir, f"{cache_key}.html")
                    screenshot_path = os.path.join(task_dir, f"{cache_key}.png") if screenshot else None
                    if not force and os.path.exists(meta_path):
                        continue
                    page = context.new_page()
                    _collect_link(
                        page,
                        url,
                        meta_path=meta_path,
                        html_path=html_path,
                        screenshot_path=screenshot_path,
                        timeout_ms=timeout_ms,
                        retries=retries,
                    )
                    page.close()

        browser.close()
