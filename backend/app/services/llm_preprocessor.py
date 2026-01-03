"""
LLM-based preprocessing for evaluation outputs using Claude Haiku.
"""

import json
import os
from typing import Any, Dict

import anthropic

client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

EXTRACTION_PROMPT = '''Extract structured data from this evaluation output.

Return ONLY valid JSON matching this exact schema:
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
- errors array: extract corrections like 'X → Should be Y' or 'Changed X to Y'
- Return ONLY JSON, no markdown, no explanation

Input:
{input}'''


def preprocess_with_haiku(raw_text: str) -> Dict[str, Any]:
    """
    Use Claude Haiku to extract structured data from raw evaluation text.

    Args:
        raw_text: Raw evaluation output text

    Returns:
        Dict with debug_info, ratings_table, errors keys
    """
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(input=raw_text)
        }]
    )

    text = response.content[0].text

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
