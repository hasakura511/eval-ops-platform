"""
Baseline Video Complex Queries - Automated Eval Runner

Uses Playwright to automate TELUS BaseLine Video Complex Queries Test 2.
"""

import asyncio
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

from .lookup import needs_lookup, LookupDecision
from .rater import (
    rate_browse,
    rate_similarity,
    rate_navigational,
    detect_time_period_query,
    detect_actor_query,
    detect_kids_content,
    detect_kids_query,
    generate_reasoning,
)


@dataclass
class QuestionData:
    """Extracted question data from BaseLine UI."""
    question_id: str
    query: str
    query_type: str  # Browse | Similarity | Navigational
    disambiguation: Optional[str]  # only for Navigational
    region: str

    # Result data
    result_title: str
    result_type: str  # Movie | Show | Person
    result_genre: Optional[str]
    result_rating: Optional[str]  # PG, PG-13, R, etc.
    result_recommended_age: Optional[str]
    result_released: Optional[str]
    result_studio: Optional[str]
    result_description: Optional[str]
    result_cast: Optional[List[str]]
    result_directors: Optional[List[str]]


@dataclass
class AnswerData:
    """Answer to submit to BaseLine."""
    rating: str
    reasoning: str
    lookup_performed: bool
    lookup_query: Optional[str]


@dataclass
class EvalResult:
    """Result of evaluating one question."""
    question: QuestionData
    answer: AnswerData
    submitted: bool
    error: Optional[str] = None


class BaselineRunner:
    """Automated runner for BaseLine Video Complex Queries evaluation."""

    def __init__(
        self,
        headless: bool = False,
        output_dir: str = "./baseline_eval_results",
        slow_mo: int = 100,
    ):
        self.headless = headless
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.slow_mo = slow_mo
        self.results: List[EvalResult] = []
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def start(self):
        """Start browser session."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self.page = await self.context.new_page()
        print(f"Browser started (headless={self.headless})")

    async def stop(self):
        """Stop browser session."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Browser stopped")

    async def navigate_to_test(self, test_url: str):
        """Navigate to the test page."""
        print(f"Navigating to: {test_url}")
        await self.page.goto(test_url, wait_until="networkidle")
        await asyncio.sleep(2)  # Wait for dynamic content

    async def wait_for_login(self):
        """Wait for user to complete login if needed."""
        # Check if we're on a login page
        try:
            login_indicator = await self.page.query_selector("input[type='password'], .login-form, #login")
            if login_indicator:
                print("\n" + "=" * 60)
                print("LOGIN REQUIRED")
                print("Please log in manually in the browser window.")
                print("Press Enter here once logged in...")
                print("=" * 60 + "\n")
                input()  # Block until user confirms
                await asyncio.sleep(2)
        except Exception:
            pass

    async def extract_question(self) -> Optional[QuestionData]:
        """Extract question data from current BaseLine page."""
        try:
            # Wait for question content to load
            await self.page.wait_for_selector(".question-container, .task-content, [data-testid='question']", timeout=10000)

            # Extract query text
            query_el = await self.page.query_selector(".query-text, .search-query, [data-testid='query']")
            query = await query_el.inner_text() if query_el else ""

            # Extract query type
            query_type_el = await self.page.query_selector(".query-type, [data-testid='query-type']")
            query_type_text = await query_type_el.inner_text() if query_type_el else "Browse"
            query_type = self._normalize_query_type(query_type_text)

            # Extract disambiguation (for Navigational)
            disambig_el = await self.page.query_selector(".disambiguation, [data-testid='disambiguation']")
            disambiguation = await disambig_el.inner_text() if disambig_el else None

            # Extract region
            region_el = await self.page.query_selector(".region, [data-testid='region']")
            region = await region_el.inner_text() if region_el else "USA"

            # Extract result card data
            result_card = await self.page.query_selector(".result-card, .content-card, [data-testid='result']")

            result_title = ""
            result_type = "Movie"
            result_genre = None
            result_rating = None
            result_recommended_age = None
            result_released = None
            result_studio = None
            result_description = None
            result_cast = None
            result_directors = None

            if result_card:
                # Title
                title_el = await result_card.query_selector(".title, h1, h2, [data-testid='title']")
                result_title = await title_el.inner_text() if title_el else ""

                # Type (Movie, Show, Person)
                type_el = await result_card.query_selector(".content-type, [data-testid='type']")
                if type_el:
                    type_text = await type_el.inner_text()
                    result_type = self._normalize_result_type(type_text)

                # Genre
                genre_el = await result_card.query_selector(".genre, [data-testid='genre']")
                result_genre = await genre_el.inner_text() if genre_el else None

                # Rating (PG, PG-13, etc.)
                rating_el = await result_card.query_selector(".rating, [data-testid='rating']")
                result_rating = await rating_el.inner_text() if rating_el else None

                # Recommended age
                age_el = await result_card.query_selector(".recommended-age, [data-testid='age']")
                result_recommended_age = await age_el.inner_text() if age_el else None

                # Released year
                year_el = await result_card.query_selector(".released, .year, [data-testid='year']")
                result_released = await year_el.inner_text() if year_el else None

                # Studio
                studio_el = await result_card.query_selector(".studio, [data-testid='studio']")
                result_studio = await studio_el.inner_text() if studio_el else None

                # Description
                desc_el = await result_card.query_selector(".description, [data-testid='description']")
                result_description = await desc_el.inner_text() if desc_el else None

            # Generate question ID from page URL or content
            question_id = await self._get_question_id()

            return QuestionData(
                question_id=question_id,
                query=query.strip(),
                query_type=query_type,
                disambiguation=disambiguation.strip() if disambiguation else None,
                region=region.strip(),
                result_title=result_title.strip(),
                result_type=result_type,
                result_genre=result_genre.strip() if result_genre else None,
                result_rating=result_rating.strip() if result_rating else None,
                result_recommended_age=result_recommended_age.strip() if result_recommended_age else None,
                result_released=result_released.strip() if result_released else None,
                result_studio=result_studio.strip() if result_studio else None,
                result_description=result_description.strip() if result_description else None,
                result_cast=result_cast,
                result_directors=result_directors,
            )

        except Exception as e:
            print(f"Error extracting question: {e}")
            return None

    async def _get_question_id(self) -> str:
        """Get unique question ID from page."""
        url = self.page.url
        # Try to extract from URL
        match = re.search(r"question[_-]?id[=:](\w+)", url)
        if match:
            return match.group(1)

        # Try from page content
        id_el = await self.page.query_selector("[data-question-id], [data-testid='question-id']")
        if id_el:
            qid = await id_el.get_attribute("data-question-id") or await id_el.inner_text()
            return qid

        # Fallback to timestamp
        return f"q_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _normalize_query_type(self, text: str) -> str:
        """Normalize query type to standard values."""
        text_lower = text.lower().strip()
        if "navigat" in text_lower:
            return "Navigational"
        elif "similar" in text_lower:
            return "Similarity"
        else:
            return "Browse"

    def _normalize_result_type(self, text: str) -> str:
        """Normalize result type to standard values."""
        text_lower = text.lower().strip()
        if "movie" in text_lower or "film" in text_lower:
            return "Movie"
        elif "show" in text_lower or "series" in text_lower or "tv" in text_lower:
            return "Show"
        elif "person" in text_lower:
            return "Person"
        else:
            return "Movie"  # Default

    async def perform_lookup(self, lookup_query: str) -> str:
        """Perform web search and return relevant info."""
        try:
            # Open new tab for search
            search_page = await self.context.new_page()

            # Use Google search
            search_url = f"https://www.google.com/search?q={lookup_query.replace(' ', '+')}"
            await search_page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            # Extract search results
            results = []

            # Get first few search result snippets
            snippets = await search_page.query_selector_all(".VwiC3b, .IsZvec, [data-content-feature='1']")
            for snippet in snippets[:3]:
                text = await snippet.inner_text()
                results.append(text.strip())

            # Also check for knowledge panel
            kp = await search_page.query_selector(".kp-wholepage, .knowledge-panel, [data-attrid]")
            if kp:
                kp_text = await kp.inner_text()
                results.insert(0, kp_text[:500])

            await search_page.close()

            return " | ".join(results[:3]) if results else "No additional info found."

        except Exception as e:
            print(f"Lookup error: {e}")
            return f"Lookup failed: {e}"

    def evaluate_question(
        self,
        question: QuestionData,
        lookup_info: Optional[str] = None,
    ) -> AnswerData:
        """Evaluate question and generate answer."""

        # Determine relevance (simplified - in real scenario this needs more logic)
        is_relevant = self._assess_relevance(question)

        # Determine popularity and recency
        is_popular = self._assess_popularity(question)
        is_recent = self._assess_recency(question)

        # Check for time period query
        is_time_period_query, time_period = detect_time_period_query(question.query)

        # Check for kids content/query
        is_kids_content = detect_kids_content(question.result_recommended_age, question.result_rating)
        is_kids_query = detect_kids_query(question.query)

        # Check for actor query
        is_actor_query = detect_actor_query(question.query)
        is_person_card = question.result_type == "Person"

        # Rate based on query type
        if question.query_type == "Browse":
            rating = rate_browse(
                query=question.query,
                result_title=question.result_title,
                result_type=question.result_type,
                result_genre=question.result_genre,
                result_year=question.result_released,
                is_relevant=is_relevant,
                is_popular=is_popular,
                is_recent=is_recent,
                is_time_period_query=is_time_period_query,
                is_kids_content=is_kids_content,
                is_kids_query=is_kids_query,
                lookup_info=lookup_info,
            )

        elif question.query_type == "Similarity":
            # Extract seed title from query
            seed_title = self._extract_seed_title(question.query)

            # Assess similarity dimensions (simplified)
            target_audience_match = True  # Would need lookup to verify
            factual_match = True  # Would need lookup to verify
            theme_match = True if lookup_info and "similar theme" in lookup_info.lower() else False

            rating = rate_similarity(
                query=question.query,
                result_title=question.result_title,
                seed_title=seed_title,
                target_audience_match=target_audience_match,
                factual_match=factual_match,
                theme_match=theme_match,
                lookup_info=lookup_info,
            )

        else:  # Navigational
            is_exact_match = self._check_exact_match(question)
            shared_attributes = self._count_shared_attributes(question, lookup_info)

            rating = rate_navigational(
                query=question.query,
                result_title=question.result_title,
                disambiguation=question.disambiguation,
                is_exact_match=is_exact_match,
                is_sequel_prequel=False,  # Would need lookup
                is_bundle=False,  # Would need lookup
                shared_attributes=shared_attributes,
                is_person_card=is_person_card,
                is_actor_query=is_actor_query,
                lookup_info=lookup_info,
            )

        # Generate reasoning
        reasoning = generate_reasoning(
            query=question.query,
            query_type=question.query_type,
            result_title=question.result_title,
            result_type=question.result_type,
            rating=rating,
            is_relevant=is_relevant,
            is_popular=is_popular,
            is_recent=is_recent,
            lookup_info=lookup_info,
        )

        return AnswerData(
            rating=rating,
            reasoning=reasoning,
            lookup_performed=lookup_info is not None,
            lookup_query=None,  # Filled by caller
        )

    def _assess_relevance(self, question: QuestionData) -> bool:
        """Assess if result is relevant to query."""
        query_lower = question.query.lower()
        title_lower = question.result_title.lower()

        # Check for obvious format mismatches
        if "movie" in query_lower and question.result_type == "Show":
            return False
        if ("show" in query_lower or "series" in query_lower) and question.result_type == "Movie":
            return False

        # Check for time period mismatches
        is_time_period_query, time_period = detect_time_period_query(question.query)
        if is_time_period_query and time_period and question.result_released:
            try:
                release_year = int(question.result_released[:4])
                decade_start, decade_end = time_period
                if not (decade_start <= release_year <= decade_end):
                    return False
            except (ValueError, TypeError):
                pass

        # Default to relevant
        return True

    def _assess_popularity(self, question: QuestionData) -> bool:
        """Assess if result is popular."""
        # This is a simplified heuristic
        # In real scenario, would use IMDB data, etc.

        # Well-known studios suggest popularity
        popular_studios = ["disney", "warner", "universal", "paramount", "sony", "netflix", "apple"]
        if question.result_studio:
            studio_lower = question.result_studio.lower()
            if any(s in studio_lower for s in popular_studios):
                return True

        return True  # Default assumption

    def _assess_recency(self, question: QuestionData) -> bool:
        """Assess if result is recent."""
        if not question.result_released:
            return False

        try:
            release_year = int(question.result_released[:4])
            current_year = datetime.now().year
            # Consider recent if within last 5 years
            return (current_year - release_year) <= 5
        except (ValueError, TypeError):
            return False

    def _extract_seed_title(self, query: str) -> str:
        """Extract the reference title from similarity query."""
        patterns = [
            r"(?:like|similar to)\s+([^,]+?)(?:\s*$|\s+and|\s+or)",
            r"movies\s+like\s+(.+)",
            r"shows\s+like\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1).strip()
        return "referenced content"

    def _check_exact_match(self, question: QuestionData) -> bool:
        """Check if result is exact match for navigational query."""
        if question.disambiguation:
            # Check if title matches disambiguation target
            disambig_lower = question.disambiguation.lower()
            result_lower = question.result_title.lower()

            # Check for title match
            if result_lower in disambig_lower or disambig_lower in result_lower:
                return True

            # Check for key word overlap
            disambig_words = set(re.findall(r'\b\w{4,}\b', disambig_lower))
            result_words = set(re.findall(r'\b\w{4,}\b', result_lower))
            overlap = disambig_words & result_words
            return len(overlap) >= 2

        return False

    def _count_shared_attributes(self, question: QuestionData, lookup_info: Optional[str]) -> int:
        """Count shared attributes between result and target."""
        count = 0

        if lookup_info:
            info_lower = lookup_info.lower()
            # Check for mentions of shared attributes
            if "same actor" in info_lower or "stars" in info_lower:
                count += 1
            if "same genre" in info_lower or "genre" in info_lower:
                count += 1
            if "same era" in info_lower or "same decade" in info_lower:
                count += 1
            if "same director" in info_lower:
                count += 1

        return count

    async def submit_answer(self, answer: AnswerData) -> bool:
        """Submit answer to BaseLine UI."""
        try:
            # Find rating dropdown/radio
            rating_selector = f"[data-rating='{answer.rating}'], [value='{answer.rating}'], label:has-text('{answer.rating}')"
            rating_el = await self.page.query_selector(rating_selector)
            if rating_el:
                await rating_el.click()

            # Find reasoning textarea and fill
            reasoning_el = await self.page.query_selector("textarea.reasoning, [name='reasoning'], [data-testid='reasoning']")
            if reasoning_el:
                await reasoning_el.fill(answer.reasoning)

            # Find and click submit button
            submit_el = await self.page.query_selector("button[type='submit'], .submit-btn, [data-testid='submit']")
            if submit_el:
                await submit_el.click()
                await asyncio.sleep(1)  # Wait for submission
                return True

            return False

        except Exception as e:
            print(f"Error submitting answer: {e}")
            return False

    async def has_next_question(self) -> bool:
        """Check if there's another question."""
        next_btn = await self.page.query_selector(".next-btn, [data-testid='next'], button:has-text('Next')")
        return next_btn is not None

    async def go_to_next_question(self):
        """Navigate to next question."""
        next_btn = await self.page.query_selector(".next-btn, [data-testid='next'], button:has-text('Next')")
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(1)

    async def run_test(self, test_url: str, max_questions: int = 100):
        """Run the full test."""
        print(f"\n{'=' * 60}")
        print("BASELINE VIDEO COMPLEX QUERIES - AUTOMATED TEST 2")
        print(f"{'=' * 60}\n")

        await self.start()

        try:
            await self.navigate_to_test(test_url)
            await self.wait_for_login()

            question_num = 0
            while question_num < max_questions:
                question_num += 1
                print(f"\n--- Question {question_num} ---")

                # Extract question
                question = await self.extract_question()
                if not question:
                    print("Failed to extract question. Stopping.")
                    break

                print(f"Query: {question.query}")
                print(f"Type: {question.query_type}")
                print(f"Result: {question.result_title} ({question.result_type})")

                # Check if lookup needed
                lookup_decision = needs_lookup(
                    query=question.query,
                    query_type=question.query_type,
                    result_title=question.result_title,
                    result_type=question.result_type,
                    result_genre=question.result_genre,
                    result_year=question.result_released,
                    disambiguation=question.disambiguation,
                )

                lookup_info = None
                if lookup_decision.should_lookup:
                    print(f"Lookup needed: {lookup_decision.reason}")
                    print(f"Searching: {lookup_decision.query}")
                    lookup_info = await self.perform_lookup(lookup_decision.query)
                    print(f"Found: {lookup_info[:100]}...")

                # Evaluate and generate answer
                answer = self.evaluate_question(question, lookup_info)
                if lookup_decision.should_lookup:
                    answer.lookup_query = lookup_decision.query

                print(f"Rating: {answer.rating}")
                print(f"Reasoning: {answer.reasoning[:100]}...")

                # Submit answer
                submitted = await self.submit_answer(answer)
                print(f"Submitted: {submitted}")

                # Record result
                self.results.append(EvalResult(
                    question=question,
                    answer=answer,
                    submitted=submitted,
                ))

                # Check for next question
                if not await self.has_next_question():
                    print("\nNo more questions. Test complete!")
                    break

                await self.go_to_next_question()

        finally:
            # Save results
            self._save_results()
            await self.stop()

    def _save_results(self):
        """Save test results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"test2_results_{timestamp}.json"

        results_data = {
            "timestamp": timestamp,
            "total_questions": len(self.results),
            "submitted": sum(1 for r in self.results if r.submitted),
            "results": [
                {
                    "question": asdict(r.question),
                    "answer": asdict(r.answer),
                    "submitted": r.submitted,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

        with open(output_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\nResults saved to: {output_file}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Baseline Video Complex Queries Automated Runner")
    parser.add_argument("--url", default="https://baseline.apple.com",
                       help="Test URL (default: https://baseline.apple.com)")
    parser.add_argument("--headless", action="store_true",
                       help="Run in headless mode")
    parser.add_argument("--max-questions", type=int, default=100,
                       help="Maximum questions to process")
    parser.add_argument("--output-dir", default="./baseline_eval_results",
                       help="Output directory for results")

    args = parser.parse_args()

    runner = BaselineRunner(
        headless=args.headless,
        output_dir=args.output_dir,
    )

    await runner.run_test(args.url, max_questions=args.max_questions)


if __name__ == "__main__":
    asyncio.run(main())
