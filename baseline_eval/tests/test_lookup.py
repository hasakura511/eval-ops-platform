"""Tests for lookup decision gate."""

import pytest
from baseline_eval.lookup import needs_lookup, LookupDecision


class TestLookupGate:
    """Test lookup decision gate logic."""

    def test_platform_query_always_lookup(self):
        """Platform availability queries should always trigger lookup."""
        result = needs_lookup(
            query="movies on hulu",
            query_type="Browse",
            result_title="The Proposal",
            result_type="Movie",
        )
        assert result.should_lookup is True
        assert "hulu" in result.query.lower()

    def test_episode_count_query_lookup(self):
        """Episode count queries should trigger lookup."""
        result = needs_lookup(
            query="shows with more than 10 episodes per season",
            query_type="Browse",
            result_title="Breaking Bad",
            result_type="Show",
        )
        assert result.should_lookup is True
        assert "episodes" in result.query.lower()

    def test_director_query_lookup(self):
        """Director queries should trigger lookup."""
        result = needs_lookup(
            query="movies by the director of inception",
            query_type="Browse",
            result_title="Tenet",
            result_type="Movie",
        )
        assert result.should_lookup is True
        assert "director" in result.query.lower()

    def test_similarity_always_lookup(self):
        """Similarity queries should always trigger lookup."""
        result = needs_lookup(
            query="movies like ex machina",
            query_type="Similarity",
            result_title="Her",
            result_type="Movie",
        )
        assert result.should_lookup is True
        assert "ex machina" in result.query.lower()

    def test_time_period_set_vs_released(self):
        """Time period queries should lookup when release year differs from queried decade."""
        result = needs_lookup(
            query="mlb movies from the 1980s",
            query_type="Browse",
            result_title="Rookie of the Year",
            result_type="Movie",
            result_year="1993",
        )
        assert result.should_lookup is True
        assert "set" in result.query.lower() or "decade" in result.query.lower()

    def test_format_mismatch_skip_lookup(self):
        """Format mismatch should skip lookup."""
        result = needs_lookup(
            query="best tv series",
            query_type="Browse",
            result_title="Top Gun",
            result_type="Movie",
        )
        assert result.should_lookup is False

    def test_metadata_sufficient_skip_lookup(self):
        """Simple browse query with matching metadata should skip lookup."""
        result = needs_lookup(
            query="action movies",
            query_type="Browse",
            result_title="Top Gun",
            result_type="Movie",
            result_genre="Action",
        )
        assert result.should_lookup is False


class TestLookupGateCalibrationExceptions:
    """Test calibration exceptions in lookup gate."""

    def test_navigational_miss_shared_attributes_lookup(self):
        """Navigational miss should lookup to verify shared attributes."""
        result = needs_lookup(
            query="old movie with eddie murphy in new york",
            query_type="Navigational",
            result_title="Beverly Hills Cop",
            result_type="Movie",
            disambiguation="Coming to America (1988)",
        )
        # Should lookup to verify shared attributes for Acceptable rating
        assert result.should_lookup is True
        assert "eddie murphy" in result.query.lower() or "coming to america" in result.query.lower()
