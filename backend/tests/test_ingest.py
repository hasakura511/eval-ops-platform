"""
Tests for ingest endpoint and LLM preprocessing.
"""

import json
import os
import pytest
import requests

from app.services.llm_preprocessor import (
    clean_llm_response,
    preprocess_with_llm,
    apply_patch_to_prompt,
)


# Sample evaluation output for testing
SIMPLE_EVAL_OUTPUT = """DEBUG INFO:
Query: best coffee shops
Result Being Evaluated: Starbucks Reserve
Result Address: 123 Main St, Seattle, WA
Classification: Highly Relevant
Result Type: POI
Distance to User (m): 500
Distance to Viewport (m): 100
Viewport Status: Inside

RATINGS TABLE:
| Field | Answer | Details |
| Pin Accuracy | Correct | Pin on building |
| Address Accuracy | Correct | Address matches |

ERRORS:
"""

EVAL_WITH_ERRORS = """DEBUG INFO:
Query: pizza near me
Result Being Evaluated: Pizza Hut
Result Address: 456 Oak Ave
Classification: Relevant
Result Type: POI
Distance to User (m): 1500
Distance to Viewport (m): 200
Viewport Status: Inside

RATINGS TABLE:
| Field | Answer | Details |
| Pin Accuracy | Wrong | Pin on street |
| Address Accuracy | Incorrect | Wrong address |

ERRORS:
Field: Pin Accuracy | From: Correct | To: Wrong | Rationale: Pin is not on building
"""

# Inline format with delimiter
INLINE_EVAL_OUTPUT = """I need you to help me evaluate this result carefully.

DEBUG INFO:
Query: coffee
Result Being Evaluated: Cafe Milano
Classification: Relevant
"""


class TestCleanLLMResponse:
    """Test the clean_llm_response function."""

    def test_clean_simple_json(self):
        """Test cleaning simple JSON."""
        text = '{"debug_info": {}, "ratings_table": [], "errors": []}'
        result = clean_llm_response(text)
        assert json.loads(result) == {"debug_info": {}, "ratings_table": [], "errors": []}

    def test_clean_with_leading_whitespace(self):
        """Test cleaning JSON with leading newlines/whitespace."""
        text = '\n  \n  {"debug_info": {"query": "test"}}'
        result = clean_llm_response(text)
        parsed = json.loads(result)
        assert parsed["debug_info"]["query"] == "test"

    def test_clean_markdown_code_block(self):
        """Test cleaning JSON wrapped in markdown code block."""
        text = '```json\n{"debug_info": {"query": "coffee"}}\n```'
        result = clean_llm_response(text)
        parsed = json.loads(result)
        assert parsed["debug_info"]["query"] == "coffee"

    def test_clean_with_text_before_json(self):
        """Test cleaning when there's text before the JSON."""
        text = 'Here is the result:\n{"debug_info": {}}'
        result = clean_llm_response(text)
        assert json.loads(result) == {"debug_info": {}}

    def test_clean_with_text_after_json(self):
        """Test cleaning when there's text after the JSON."""
        text = '{"errors": []}\n\nI hope this helps!'
        result = clean_llm_response(text)
        assert json.loads(result) == {"errors": []}

    def test_clean_empty_string(self):
        """Test cleaning empty string returns empty object."""
        result = clean_llm_response("")
        assert result == "{}"

    def test_clean_no_json(self):
        """Test cleaning text with no JSON returns empty object."""
        result = clean_llm_response("This has no JSON at all")
        assert result == "{}"


class TestOllamaDirect:
    """Test Ollama LLM directly (requires Ollama running on host)."""

    @pytest.fixture(autouse=True)
    def check_ollama(self):
        """Skip tests if Ollama is not running."""
        try:
            # Use localhost for direct testing (not from Docker)
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code != 200:
                pytest.skip("Ollama not running")
        except requests.exceptions.RequestException:
            pytest.skip("Ollama not accessible")

    def test_ollama_simple_eval(self):
        """Test Ollama preprocessing with simple eval output."""
        # Override URL for local testing
        os.environ["OLLAMA_URL"] = "http://localhost:11434/api/generate"

        result = preprocess_with_llm(SIMPLE_EVAL_OUTPUT)

        assert "debug_info" in result
        assert "ratings_table" in result
        assert "errors" in result
        assert result["debug_info"].get("query") == "best coffee shops"

    def test_ollama_eval_with_errors(self):
        """Test Ollama preprocessing with errors in output."""
        os.environ["OLLAMA_URL"] = "http://localhost:11434/api/generate"

        result = preprocess_with_llm(EVAL_WITH_ERRORS)

        assert "debug_info" in result
        assert len(result.get("errors", [])) > 0 or len(result.get("ratings_table", [])) > 0


class TestDockerOllamaConnection:
    """Test Docker container can reach Ollama on host."""

    @pytest.fixture(autouse=True)
    def check_docker(self):
        """Skip tests if Docker is not running."""
        try:
            result = os.popen("docker compose ps --format json 2>/dev/null").read()
            if not result or "backend" not in result:
                pytest.skip("Docker services not running")
        except Exception:
            pytest.skip("Docker not accessible")

    def test_docker_to_ollama_connection(self):
        """Test that Docker backend can reach Ollama via host.docker.internal."""
        # Call the ingest endpoint which uses Ollama from Docker
        try:
            resp = requests.post(
                "http://localhost:8000/api/v1/ingest/",
                json={"raw_text": SIMPLE_EVAL_OUTPUT},
                timeout=120  # LLM can be slow
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "parsed" in data
            assert "debug_info" in data["parsed"]
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Backend not accessible: {e}")


class TestIngestEndpoint:
    """Test the ingest API endpoint."""

    @pytest.fixture(autouse=True)
    def check_backend(self):
        """Skip tests if backend is not running."""
        try:
            resp = requests.get("http://localhost:8000/health", timeout=5)
            # Accept 200 or 404 (endpoint may not exist)
            if resp.status_code not in [200, 404]:
                pytest.skip("Backend not healthy")
        except requests.exceptions.RequestException:
            pytest.skip("Backend not accessible")

    def test_ingest_simple_format(self):
        """Test ingest with simple eval output format."""
        resp = requests.post(
            "http://localhost:8000/api/v1/ingest/",
            json={"raw_text": SIMPLE_EVAL_OUTPUT},
            timeout=120
        )

        assert resp.status_code == 200
        data = resp.json()

        assert "submission_id" in data
        assert "parsed" in data
        assert data["parsed"]["debug_info"].get("query") == "best coffee shops"

    def test_ingest_with_model_info(self):
        """Test ingest with model name and version."""
        resp = requests.post(
            "http://localhost:8000/api/v1/ingest/",
            json={
                "raw_text": SIMPLE_EVAL_OUTPUT,
                "model_name": "claude-3-5-sonnet",
                "model_version": "20241022",
            },
            timeout=120
        )

        assert resp.status_code == 200
        data = resp.json()

        assert data.get("model_name") == "claude-3-5-sonnet"
        assert data.get("model_version") == "20241022"

    def test_ingest_with_inline_prompt(self):
        """Test ingest with inline agent prompt (prefix detection)."""
        resp = requests.post(
            "http://localhost:8000/api/v1/ingest/",
            json={"raw_text": INLINE_EVAL_OUTPUT},
            timeout=120
        )

        assert resp.status_code == 200
        data = resp.json()

        # Should have detected and extracted agent prompt
        assert "agent_prompt" in data

    def test_ingest_with_explicit_prompt(self):
        """Test ingest with explicit agent_prompt field."""
        resp = requests.post(
            "http://localhost:8000/api/v1/ingest/",
            json={
                "raw_text": SIMPLE_EVAL_OUTPUT,
                "agent_prompt": "Evaluate this carefully",
            },
            timeout=120
        )

        assert resp.status_code == 200
        data = resp.json()

        assert data.get("agent_prompt") == "Evaluate this carefully"

    def test_ingest_empty_text_rejected(self):
        """Test that empty raw_text is rejected."""
        resp = requests.post(
            "http://localhost:8000/api/v1/ingest/",
            json={"raw_text": ""},
            timeout=30
        )

        assert resp.status_code == 400


class TestApplyPatchToPrompt:
    """Unit tests for prompt patching helper."""

    def test_fallback_when_llm_response_invalid(self, monkeypatch):
        """LLM failures should return a deterministic fallback patch."""

        def fake_post(*args, **kwargs):
            class DummyResponse:
                def raise_for_status(self):
                    return None

                def json(self):
                    # Missing JSON object to force fallback
                    return {"response": "not-json"}

            return DummyResponse()

        monkeypatch.setattr("app.services.llm_preprocessor.requests.post", fake_post)

        result = apply_patch_to_prompt(
            current_prompt="Current prompt text",
            patch_suggestions="- Add new safety check",
            current_version="v1.0",
        )

        assert result["verified"] is False
        assert result["new_version"] == "v1.1"
        assert "- Add new safety check" in result["updated_prompt"]
        assert any(entry.get("location") == "Fallback" for entry in result.get("changelog", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
