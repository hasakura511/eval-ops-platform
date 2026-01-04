"""
LLM-based preprocessing for evaluation outputs using local Ollama.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def clean_llm_response(text: str) -> str:
    """
    Clean LLM response to extract valid JSON.

    Handles:
    - Leading/trailing whitespace and newlines
    - Markdown code blocks (```json ... ```)
    - Text before/after JSON object
    - Escaped characters

    Args:
        text: Raw LLM response text

    Returns:
        Cleaned JSON string
    """
    if not text:
        return "{}"

    original = text
    logger.debug(f"Cleaning LLM response, length={len(text)}")

    # Strip whitespace
    text = text.strip()

    # Remove markdown code blocks
    if text.startswith("```"):
        # Find the end of the opening fence
        first_newline = text.find("\n")
        if first_newline != -1:
            # Skip ```json or ``` line
            text = text[first_newline + 1:]
        # Remove closing fence
        if "```" in text:
            text = text[:text.rfind("```")]
        text = text.strip()

    # Find JSON object boundaries
    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        logger.warning(f"No valid JSON object found in response: {text[:200]}...")
        return "{}"

    # Extract just the JSON portion
    text = text[start_idx:end_idx + 1]

    logger.debug(f"Cleaned JSON, length={len(text)}")

    return text

# Ollama configuration - use host.docker.internal to access host from Docker
DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:14b"


def get_ollama_url() -> str:
    """Get Ollama URL, checking environment at runtime."""
    return os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)


def get_ollama_model() -> str:
    """Get Ollama model, checking environment at runtime."""
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

EXTRACTION_PROMPT = '''Extract structured data from this evaluation output.
Return ONLY valid JSON matching this schema:
{{
  "debug_info": {{
    "query": string or null,
    "result_being_evaluated": string or null,
    "result_address": string or null,
    "classification": string or null,
    "result_type": string or null,
    "distance_to_user_m": number or null,
    "distance_to_viewport_m": number or null,
    "viewport_status": string or null
  }},
  "ratings_table": [
    {{"field": string, "answer": string, "details": string}}
  ],
  "errors": [
    {{"index": number, "field": string or null, "from_value": string or null, "to_value": string or null, "rationale_text": string or null}}
  ]
}}

Rules:
- Convert distances to meters (973 m = 973, 1.5 km = 1500)
- If a field is missing, use null
- Extract corrections like 'X → Should be Y' or 'Changed X to Y' into errors array
- Return ONLY JSON, no markdown, no explanation

Input:
{input}'''


def preprocess_with_llm(raw_text: str) -> Dict[str, Any]:
    """
    Use local Ollama LLM to extract structured data from raw evaluation text.

    Args:
        raw_text: Raw evaluation output text

    Returns:
        Dict with debug_info, ratings_table, errors keys
    """
    ollama_url = get_ollama_url()
    model = get_ollama_model()

    logger.info(f"Calling Ollama at {ollama_url} with model {model}")
    logger.debug(f"Input text length: {len(raw_text)}")

    try:
        response = requests.post(
            ollama_url,
            json={
                "model": model,
                "prompt": EXTRACTION_PROMPT.format(input=raw_text),
                "stream": False,
                "format": "json"
            },
            timeout=120
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        raise

    result = response.json()
    raw_response = result.get("response", "{}")

    logger.debug(f"Raw Ollama response: {raw_response[:500]}...")

    # Clean the response to extract valid JSON
    cleaned = clean_llm_response(raw_response)

    try:
        parsed = json.loads(cleaned)
        logger.info("Successfully parsed Ollama JSON response")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.error(f"Cleaned text was: {cleaned[:500]}...")
        raise

    # Ensure required keys exist with defaults
    if "debug_info" not in parsed:
        parsed["debug_info"] = {}
    if "ratings_table" not in parsed:
        parsed["ratings_table"] = []
    if "errors" not in parsed:
        parsed["errors"] = []

    return parsed


# Keep Haiku as fallback option
def preprocess_with_haiku(raw_text: str) -> Dict[str, Any]:
    """
    Use Claude Haiku to extract structured data (fallback if Ollama unavailable).
    """
    logger.info("Calling Haiku as fallback")

    try:
        import anthropic
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(input=raw_text)
            }]
        )

        raw_response = response.content[0].text
        logger.debug(f"Raw Haiku response: {raw_response[:500]}...")

        # Use same cleaning function
        cleaned = clean_llm_response(raw_response)

        try:
            parsed = json.loads(cleaned)
            logger.info("Successfully parsed Haiku JSON response")
        except json.JSONDecodeError as e:
            logger.error(f"Haiku JSON parse error: {e}")
            logger.error(f"Cleaned text was: {cleaned[:500]}...")
            raise

        if "debug_info" not in parsed:
            parsed["debug_info"] = {}
        if "ratings_table" not in parsed:
            parsed["ratings_table"] = []
        if "errors" not in parsed:
            parsed["errors"] = []

        return parsed
    except Exception as e:
        logger.warning(f"Haiku fallback failed: {e}")
        raise


PATCH_PROMPT = '''You are an expert at applying patches to agent prompts.

Given the CURRENT PROMPT and PATCH SUGGESTIONS, apply the changes and return the updated prompt.

CURRENT VERSION: {current_version}

CURRENT PROMPT:
{current_prompt}

PATCH SUGGESTIONS:
{patch_suggestions}

Instructions:
1. Apply each patch suggestion to the prompt
2. Use clear section references (e.g., §6.6.5, §9)
3. Increment the version number (e.g., v1.0 → v1.1)
4. Track what changes you made

Return ONLY valid JSON matching this schema:
{{
  "updated_prompt": "The full updated prompt text with all changes applied",
  "new_version": "v1.X",
  "changelog": [
    {{"action": "Add|Replace|Remove", "location": "§X.X", "description": "Brief description of change"}}
  ],
  "verification_notes": "Brief notes confirming changes were applied correctly"
}}

Return ONLY JSON, no markdown, no explanation.'''


def apply_patch_to_prompt(
    current_prompt: str,
    patch_suggestions: str,
    current_version: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use LLM to apply patch suggestions to an agent prompt.

    Args:
        current_prompt: The current agent prompt text
        patch_suggestions: The suggested patches to apply
        current_version: Current version string (e.g., 'v1.0')

    Returns:
        Dict with updated_prompt, new_version, changelog, verification_notes
    """
    if not current_version:
        current_version = "v1.0"

    prompt = PATCH_PROMPT.format(
        current_version=current_version,
        current_prompt=current_prompt,
        patch_suggestions=patch_suggestions
    )

    ollama_url = get_ollama_url()
    model = get_ollama_model()

    logger.info(f"Applying patch to prompt using {model}")

    try:
        response = requests.post(
            ollama_url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )
        response.raise_for_status()

        result = response.json()
        raw_response = result.get("response", "{}")
        cleaned = clean_llm_response(raw_response)

        parsed = json.loads(cleaned)
        logger.info("Successfully applied patch to prompt")

        # Ensure required keys exist
        if "updated_prompt" not in parsed:
            raise ValueError("LLM response missing 'updated_prompt'")
        if "new_version" not in parsed:
            parsed["new_version"] = _increment_version(current_version)
        if "changelog" not in parsed:
            parsed["changelog"] = []
        if "verification_notes" not in parsed:
            parsed["verification_notes"] = "Changes applied"

        return parsed

    except Exception as e:
        logger.error(f"Failed to apply patch: {e}")
        raise


def _increment_version(version: str) -> str:
    """Increment version number (e.g., v1.0 → v1.1, v1.9 → v1.10)."""
    import re
    match = re.match(r'v?(\d+)\.(\d+)', version)
    if match:
        major, minor = int(match.group(1)), int(match.group(2))
        return f"v{major}.{minor + 1}"
    return "v1.1"
