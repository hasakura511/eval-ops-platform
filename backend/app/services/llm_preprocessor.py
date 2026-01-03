"""
LLM-based preprocessing for evaluation outputs using local Ollama.
"""

import json
import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

# Ollama configuration - use host.docker.internal to access host from Docker
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/api/generate")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

EXTRACTION_PROMPT = '''Extract structured data from this evaluation output.
Return ONLY valid JSON matching this schema:
{
  "debug_info": {
    "query": string or null,
    "result_being_evaluated": string or null,
    "result_address": string or null,
    "classification": string or null,
    "result_type": string or null,
    "distance_to_user_m": number or null,
    "distance_to_viewport_m": number or null,
    "viewport_status": string or null
  },
  "ratings_table": [
    {"field": string, "answer": string, "details": string}
  ],
  "errors": [
    {"index": number, "field": string or null, "from_value": string or null, "to_value": string or null, "rationale_text": string or null}
  ]
}

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
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": EXTRACTION_PROMPT.format(input=raw_text),
            "stream": False,
            "format": "json"
        },
        timeout=60
    )
    response.raise_for_status()

    result = response.json()
    text = result.get("response", "{}")

    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("```")
        if len(lines) >= 2:
            text = lines[1]
            if text.startswith("json"):
                text = text[4:]

    parsed = json.loads(text.strip())

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

        text = response.content[0].text

        if text.startswith("```"):
            lines = text.split("```")
            if len(lines) >= 2:
                text = lines[1]
                if text.startswith("json"):
                    text = text[4:]

        parsed = json.loads(text.strip())

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
