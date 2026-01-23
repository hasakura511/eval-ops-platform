"""Tests for rating logic."""

import pytest
from baseline_eval.rater import (
    rate_browse,
    rate_similarity,
    rate_navigational,
    detect_time_period_query,
    detect_actor_query,
    detect_kids_content,
    detect_kids_query,
    generate_reasoning,
)


class TestBrowseRating:
    """Test Browse query rating logic."""

    def test_relevant_popular_recent_excellent(self):
        """Relevant + Popular + Recent = Excellent."""
        rating = rate_browse(
            query="action movies",
            result_title="Top Gun: Maverick",
            result_type="Movie",
            result_genre="Action",
            result_year="2022",
            is_relevant=True,
            is_popular=True,
            is_recent=True,
        )
        assert rating == "Excellent"

    def test_relevant_popular_not_recent_good(self):
        """Relevant + Popular + Not Recent = Good."""
        rating = rate_browse(
            query="action movies",
            result_title="Top Gun",
            result_type="Movie",
            result_genre="Action",
            result_year="1986",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
        )
        assert rating == "Good"

    def test_relevant_not_popular_recent_good(self):
        """Relevant + Not Popular + Recent = Good."""
        rating = rate_browse(
            query="action movies",
            result_title="Unknown Action",
            result_type="Movie",
            result_genre="Action",
            result_year="2023",
            is_relevant=True,
            is_popular=False,
            is_recent=True,
        )
        assert rating == "Good"

    def test_relevant_not_popular_not_recent_acceptable(self):
        """Relevant + Not Popular + Not Recent = Acceptable."""
        rating = rate_browse(
            query="action movies",
            result_title="Old Unknown",
            result_type="Movie",
            result_genre="Action",
            result_year="1995",
            is_relevant=True,
            is_popular=False,
            is_recent=False,
        )
        assert rating == "Acceptable"

    def test_not_relevant_off_topic(self):
        """Not Relevant = Off-Topic."""
        rating = rate_browse(
            query="action movies",
            result_title="The Notebook",
            result_type="Movie",
            result_genre="Romance",
            result_year="2004",
            is_relevant=False,
            is_popular=True,
            is_recent=False,
        )
        assert rating == "Off-Topic"

    def test_time_period_waives_recency(self):
        """Time period queries waive recency requirement."""
        rating = rate_browse(
            query="best 80s movies",
            result_title="Top Gun",
            result_type="Movie",
            result_genre="Action",
            result_year="1986",
            is_relevant=True,
            is_popular=True,
            is_recent=False,  # Not recent but waived
            is_time_period_query=True,
        )
        assert rating == "Excellent"

    def test_kids_content_demotion(self):
        """Kids content should be demoted by 1 level."""
        rating = rate_browse(
            query="comedy movies",
            result_title="Secret Life of Pets",
            result_type="Movie",
            result_genre="Animation",
            result_year="2016",
            is_relevant=True,
            is_popular=True,
            is_recent=True,
            is_kids_content=True,
            is_kids_query=False,
        )
        assert rating == "Good"  # Demoted from Excellent

    def test_kids_content_no_demotion_for_kids_query(self):
        """Kids content should NOT be demoted for kids queries."""
        rating = rate_browse(
            query="kids animated movies",
            result_title="Secret Life of Pets",
            result_type="Movie",
            result_genre="Animation",
            result_year="2016",
            is_relevant=True,
            is_popular=True,
            is_recent=True,
            is_kids_content=True,
            is_kids_query=True,
        )
        assert rating == "Excellent"


class TestSimilarityRating:
    """Test Similarity query rating logic."""

    def test_all_three_match_excellent(self):
        """3/3 categories = Excellent."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Her",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=True,
            theme_match=True,
        )
        assert rating == "Excellent"

    def test_two_match_good(self):
        """2/3 categories = Good."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Her",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=True,
            theme_match=False,
        )
        assert rating == "Good"

    def test_one_match_acceptable(self):
        """1/3 categories = Acceptable."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Blacksad",
            seed_title="Ex Machina",
            target_audience_match=False,
            factual_match=True,
            theme_match=False,
        )
        assert rating == "Acceptable"

    def test_no_match_off_topic(self):
        """0/3 categories = Off-Topic."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Just Go with It",
            seed_title="Ex Machina",
            target_audience_match=False,
            factual_match=False,
            theme_match=False,
        )
        assert rating == "Off-Topic"


class TestNavigationalRating:
    """Test Navigational query rating logic."""

    def test_exact_match_perfect(self):
        """Exact match = Perfect."""
        rating = rate_navigational(
            query="jurassic park movie",
            result_title="Jurassic Park",
            disambiguation="Jurassic Park (1993)",
            is_exact_match=True,
        )
        assert rating == "Perfect"

    def test_sequel_prequel_excellent(self):
        """Sequel/prequel = Excellent."""
        rating = rate_navigational(
            query="jurassic park movies",
            result_title="Jurassic World",
            disambiguation="Jurassic Park",
            is_exact_match=False,
            is_sequel_prequel=True,
        )
        assert rating == "Excellent"

    def test_person_card_for_actor_query_excellent(self):
        """Person card for actor query = Excellent (calibration exception)."""
        rating = rate_navigational(
            query="movies starring emma watson",
            result_title="Emma Watson",
            disambiguation=None,
            is_exact_match=False,
            is_person_card=True,
            is_actor_query=True,
        )
        assert rating == "Excellent"

    def test_navigational_miss_shared_attributes_acceptable(self):
        """Navigational miss with shared attributes = Acceptable (calibration exception)."""
        rating = rate_navigational(
            query="old movie with eddie murphy in new york",
            result_title="Beverly Hills Cop",
            disambiguation="Coming to America (1988)",
            is_exact_match=False,
            shared_attributes=2,  # same actor + same genre
        )
        assert rating == "Acceptable"

    def test_navigational_miss_no_attributes_off_topic(self):
        """Navigational miss with no shared attributes = Off-Topic."""
        rating = rate_navigational(
            query="that movie with the blue people",
            result_title="Good Luck Chuck",
            disambiguation="Avatar",
            is_exact_match=False,
            shared_attributes=0,
        )
        assert rating == "Off-Topic"


class TestDetectors:
    """Test detection helper functions."""

    def test_detect_time_period_query_80s(self):
        """Detect 80s time period query."""
        is_tp, period = detect_time_period_query("best 80s movies")
        assert is_tp is True
        assert period == (1980, 1989)

    def test_detect_time_period_query_1980s(self):
        """Detect 1980s time period query."""
        is_tp, period = detect_time_period_query("action movies from the 1980s")
        assert is_tp is True
        assert period == (1980, 1989)

    def test_detect_time_period_query_none(self):
        """No time period in query."""
        is_tp, period = detect_time_period_query("best action movies")
        assert is_tp is False
        assert period is None

    def test_detect_actor_query_starring(self):
        """Detect actor query with 'starring'."""
        assert detect_actor_query("movies starring tom hanks") is True

    def test_detect_actor_query_with(self):
        """Detect actor query with 'movies with'."""
        assert detect_actor_query("movies with tom hanks") is True

    def test_detect_kids_content_age(self):
        """Detect kids content by age rating."""
        assert detect_kids_content("7+", None) is True
        assert detect_kids_content("13+", None) is False

    def test_detect_kids_content_rating(self):
        """Detect kids content by content rating."""
        assert detect_kids_content(None, "G") is True
        assert detect_kids_content(None, "R") is False

    def test_detect_kids_query(self):
        """Detect kids-specific query."""
        assert detect_kids_query("animated movies for kids") is True
        assert detect_kids_query("action movies") is False


class TestReasoning:
    """Test reasoning generation."""

    def test_reasoning_no_bullets(self):
        """Reasoning should not contain bullets."""
        reasoning = generate_reasoning(
            query="action movies from the 80s",
            query_type="Browse",
            result_title="Top Gun",
            result_type="Movie",
            rating="Excellent",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
        )
        assert "-" not in reasoning or "Top Gun" in reasoning
        assert "*" not in reasoning
        assert "1." not in reasoning

    def test_reasoning_contains_abbreviation_expansion(self):
        """Reasoning should expand abbreviations."""
        reasoning = generate_reasoning(
            query="best rom-com movies",
            query_type="Browse",
            result_title="The Proposal",
            result_type="Movie",
            rating="Good",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
        )
        assert "romantic comedy" in reasoning.lower()

    def test_reasoning_is_single_paragraph(self):
        """Reasoning should be a single paragraph."""
        reasoning = generate_reasoning(
            query="action movies",
            query_type="Browse",
            result_title="Top Gun",
            result_type="Movie",
            rating="Excellent",
            is_relevant=True,
            is_popular=True,
            is_recent=True,
        )
        # Should not have multiple paragraphs
        paragraphs = [p for p in reasoning.split("\n\n") if p.strip()]
        assert len(paragraphs) == 1
