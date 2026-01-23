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
    # New helper functions (Bug fixes)
    is_classic_content,
    is_atv_plus_content,
    has_major_awards,
    is_ultra_popular,
    demote_rating,
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

    def test_time_period_popular_no_award_good(self):
        """Time period queries: Popular (no award) = Good per image_12.png."""
        rating = rate_browse(
            query="best 80s movies",
            result_title="Top Gun",
            result_type="Movie",
            result_genre="Action",
            result_year="1986",
            is_relevant=True,
            is_popular=True,
            is_recent=False,  # Recency irrelevant for time period
            is_time_period_query=True,
        )
        # Per image_12.png: Popular + No Award = Good (not Excellent)
        assert rating == "Good"

    def test_time_period_ultra_popular_excellent(self):
        """Time period queries: Ultra-popular = Excellent regardless of awards."""
        rating = rate_browse(
            query="best 80s movies",
            result_title="Top Gun",
            result_type="Movie",
            result_genre="Action",
            result_year="1986",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
            is_time_period_query=True,
            imdb_rating_count=600000,  # Ultra-popular: >500K
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


# =============================================================================
# Bug Fix Tests (handoff-2026-01-24-code-001)
# =============================================================================


class TestBug1TargetAudienceAloneIsGood:
    """Bug 1: Target Audience alone = Good (not Acceptable).

    Per image_06.png row 5: Yes/No/No (Target Audience only) = Good.
    """

    def test_target_audience_alone_is_good(self):
        """Target Audience match alone should be Good, not Acceptable."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Her",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=False,
            theme_match=False,
        )
        assert rating == "Good"  # NOT Acceptable

    def test_factual_alone_is_acceptable(self):
        """Factual match alone should still be Acceptable."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Blacksad",
            seed_title="Ex Machina",
            target_audience_match=False,
            factual_match=True,
            theme_match=False,
        )
        assert rating == "Acceptable"

    def test_theme_alone_is_acceptable(self):
        """Theme match alone should still be Acceptable."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Other Movie",
            seed_title="Ex Machina",
            target_audience_match=False,
            factual_match=False,
            theme_match=True,
        )
        assert rating == "Acceptable"


class TestBug2ClassicContentIgnoresRecency:
    """Bug 2: Classic content ignores recency.

    Per guideline 2.2.3.2:
    "Ignore recency for classic movies and tv shows that were among the
    most popular in their decade or have high popularity today."
    """

    def test_is_classic_content_high_ratings(self):
        """Content with >100K IMDB ratings is classic."""
        assert is_classic_content("The Shawshank Redemption", 1994, 250000) is True

    def test_is_classic_content_old_with_moderate_ratings(self):
        """Old content (pre-2010) with >50K ratings is classic."""
        assert is_classic_content("Old Classic", 2005, 60000) is True

    def test_is_classic_content_not_classic(self):
        """Recent content with few ratings is not classic."""
        assert is_classic_content("New Movie", 2023, 10000) is False

    def test_classic_content_waives_recency_in_browse(self):
        """Classic content should get recency waived in rate_browse()."""
        rating = rate_browse(
            query="drama movies",
            result_title="The Shawshank Redemption",
            result_type="Movie",
            result_genre="Drama",
            result_year="1994",
            is_relevant=True,
            is_popular=True,
            is_recent=False,  # Not recent but should be waived
            imdb_rating_count=250000,  # Classic: >100K ratings
        )
        # Should be Excellent (popular + recency waived) not just Good
        assert rating == "Excellent"


class TestBug3ATVPlusBenefitOfDoubt:
    """Bug 3: AppleTV+ benefit of doubt (Good → Excellent).

    Per guideline 2.2.2.1:
    "Popularity is slightly less strict for ATV+ content.
    If in doubt about 'Good' or 'Excellent' for ATV+ result, select 'Excellent'"
    """

    def test_is_atv_plus_content_true(self):
        """Detect Apple TV+ content."""
        assert is_atv_plus_content("Apple TV+") is True
        assert is_atv_plus_content("ATV+") is True
        assert is_atv_plus_content("Apple TV Plus") is True

    def test_is_atv_plus_content_false(self):
        """Non-ATV+ sources return False."""
        assert is_atv_plus_content("Netflix") is False
        assert is_atv_plus_content(None) is False

    def test_atv_plus_good_becomes_excellent(self):
        """ATV+ content at Good should be upgraded to Excellent."""
        rating = rate_browse(
            query="comedy shows",
            result_title="Ted Lasso",
            result_type="Show",
            result_genre="Comedy",
            result_year="2023",
            is_relevant=True,
            is_popular=True,
            is_recent=False,  # Would be Good normally
            result_source="Apple TV+",
        )
        assert rating == "Excellent"  # Upgraded from Good


class TestBug4TimePeriodPlusAwardsExcellent:
    """Bug 4: Time Period + Popular + Awards = Excellent.

    Per image_12.png (Time Period matrix):
    - Relevant + Popular + Award = Excellent
    - Relevant + Ultra-popular (no award needed) = Excellent
    - Relevant + Popular + No Award = Good
    """

    def test_has_major_awards_true(self):
        """Detect content with major awards."""
        assert has_major_awards("Won Oscar for Best Picture") is True
        assert has_major_awards("Emmy Award winner") is True
        assert has_major_awards("Golden Globe winner") is True

    def test_has_major_awards_false(self):
        """Content without major awards."""
        assert has_major_awards("Some random info") is False
        assert has_major_awards(None) is False

    def test_time_period_popular_with_award_excellent(self):
        """Time period query + popular + award = Excellent."""
        rating = rate_browse(
            query="best 2000s dramas",
            result_title="The Wire",
            result_type="Show",
            result_genre="Drama",
            result_year="2002",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
            is_time_period_query=True,
            lookup_info="Won Emmy Award for Best Drama",
        )
        assert rating == "Excellent"

    def test_time_period_popular_no_award_good(self):
        """Time period query + popular + no award = Good."""
        rating = rate_browse(
            query="best 2000s dramas",
            result_title="Some Popular Show",
            result_type="Show",
            result_genre="Drama",
            result_year="2005",
            is_relevant=True,
            is_popular=True,
            is_recent=False,
            is_time_period_query=True,
            lookup_info="Popular but no awards",  # No award keywords
        )
        assert rating == "Good"


class TestBug5UltraPopularDetection:
    """Bug 5: Ultra-popular detection.

    Per guideline 3.4.1 (Time Period):
    "Excellent = Top 50 viewed in decade / Top 10 in year"
    """

    def test_is_ultra_popular_imdb_rank(self):
        """IMDB top 250 is ultra-popular."""
        assert is_ultra_popular(imdb_rank=100, imdb_rating_count=None) is True
        assert is_ultra_popular(imdb_rank=250, imdb_rating_count=None) is True

    def test_is_ultra_popular_high_ratings(self):
        """Content with >500K ratings is ultra-popular."""
        assert is_ultra_popular(imdb_rank=None, imdb_rating_count=600000) is True

    def test_is_ultra_popular_false(self):
        """Content that doesn't meet ultra-popular thresholds."""
        assert is_ultra_popular(imdb_rank=500, imdb_rating_count=100000) is False
        assert is_ultra_popular(imdb_rank=None, imdb_rating_count=None) is False

    def test_ultra_popular_time_period_excellent(self):
        """Ultra-popular content in time period query = Excellent (regardless of awards)."""
        rating = rate_browse(
            query="best 80s movies",
            result_title="The Outsiders",
            result_type="Movie",
            result_genre="Drama",
            result_year="1983",
            is_relevant=True,
            is_popular=False,  # Not "popular" by normal standards
            is_recent=False,
            is_time_period_query=True,
            imdb_rank=200,  # But ultra-popular by IMDB rank
        )
        assert rating == "Excellent"


class TestBug6SimilarityOnNavigationalDemotion:
    """Bug 6: Similarity results on Navigational queries = Demote by 1.

    Per image_10.png: When similarity results appear on navigational queries,
    demote ALL ratings by 1 level:
    - Excellent → Good
    - Good → Acceptable
    - Acceptable → Off-Topic
    """

    def test_demote_rating_function(self):
        """Test demote_rating helper function."""
        assert demote_rating("Perfect") == "Excellent"
        assert demote_rating("Excellent") == "Good"
        assert demote_rating("Good") == "Acceptable"
        assert demote_rating("Acceptable") == "Off-Topic"
        assert demote_rating("Off-Topic") == "Off-Topic"  # Can't demote further

    def test_similarity_on_navigational_excellent_to_good(self):
        """3/3 match on navigational becomes Good (not Excellent)."""
        rating = rate_similarity(
            query="the robot movie where a guy falls in love",
            result_title="Her",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=True,
            theme_match=True,
            on_navigational_query=True,
        )
        assert rating == "Good"  # Demoted from Excellent

    def test_similarity_on_navigational_good_to_acceptable(self):
        """2/3 match on navigational becomes Acceptable (not Good)."""
        rating = rate_similarity(
            query="the robot movie where a guy falls in love",
            result_title="Some Movie",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=True,
            theme_match=False,
            on_navigational_query=True,
        )
        assert rating == "Acceptable"  # Demoted from Good

    def test_similarity_on_navigational_acceptable_to_off_topic(self):
        """1/3 match (factual only) on navigational becomes Off-Topic."""
        rating = rate_similarity(
            query="the robot movie where a guy falls in love",
            result_title="Blacksad",
            seed_title="Ex Machina",
            target_audience_match=False,
            factual_match=True,
            theme_match=False,
            on_navigational_query=True,
        )
        assert rating == "Off-Topic"  # Demoted from Acceptable

    def test_similarity_regular_not_demoted(self):
        """Similarity on non-navigational should NOT be demoted."""
        rating = rate_similarity(
            query="movies like ex machina",
            result_title="Her",
            seed_title="Ex Machina",
            target_audience_match=True,
            factual_match=True,
            theme_match=True,
            on_navigational_query=False,  # Regular similarity query
        )
        assert rating == "Excellent"  # NOT demoted
