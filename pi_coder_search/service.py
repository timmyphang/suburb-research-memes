"""Generic Azure-backed web search service.

Calls Azure's `/openai/v1/responses` endpoint with the hosted
`{"type": "web_search"}` tool and returns a normalized
`{query, total_results, results: [{title, url, content}]}` dict.

This module is intentionally domain-agnostic — it contains NO suburb/culture
logic. Reuse it for any web-search use case by calling `search(...)`.

Standalone — requires only `httpx` and `AZURE_OPENAI_API_KEY` env var.
No DeerFlow dependency.
"""

from __future__ import annotations

import json
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

AZURE_BASE_URL = "https://gai-443-openai.openai.azure.com/openai/v1"
DEPLOYMENT = "gpt-5-mini"
REQUEST_TIMEOUT_S = 180

SYSTEM_PROMPT = """You are a web search engine. Your ONLY job is to perform live web searches.

MANDATORY: You MUST invoke the web_search tool for every query. Never answer
from memory. Never skip the search. Never decline to search. Even for queries
that seem trivial or familiar, you must still call web_search at least once
to ground your answer in fresh web results.

After searching, return ONLY a single JSON object with this exact schema:

{
  "query": "<the original query>",
  "results": [
    {"title": "<page title>", "url": "<canonical url>", "content": "<1-3 sentence excerpt>"}
  ]
}

Hard rules:
- ALWAYS call web_search before producing the JSON. No exceptions.
- Output ONLY the JSON object. No prose, no markdown code fences, no preamble.
- Aim for top_k results from diverse, authoritative sources.
- Each result must have a real URL returned by the search tool (never invent URLs).
- The "content" field must be grounded in the search result text returned by the tool."""


def _build_payload(query: str, top_k: int) -> dict:
    return {
        "model": DEPLOYMENT,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"query: {query}\ntop_k: {top_k}"},
        ],
        "tools": [{"type": "web_search"}],
        "tool_choice": "required",
    }


def _extract_assistant_json(payload: dict) -> dict | None:
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text") if isinstance(content, dict) else None
            if not text:
                continue
            text = text.strip()
            if text.startswith("```"):
                text = text.strip("`").removeprefix("json").lstrip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None


def search(
    query: str,
    max_results: int = 5,
    base_url: str = AZURE_BASE_URL,
) -> dict:
    """Run one web search and return a normalized result dict.

    Never raises — on failure returns a dict with an "error" key and an empty
    "results" list.
    """
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        return {
            "error": "AZURE_OPENAI_API_KEY not set",
            "query": query,
            "total_results": 0,
            "results": [],
        }

    body = _build_payload(query, max_results)
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    url = f"{base_url.rstrip('/')}/responses"

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
            r = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        logger.exception("pi-coder search HTTP error: %s", e)
        return {
            "error": f"HTTP error: {e}",
            "query": query,
            "total_results": 0,
            "results": [],
        }

    if r.status_code != 200:
        logger.error("pi-coder search HTTP %s: %s", r.status_code, r.text[:500])
        return {
            "error": f"HTTP {r.status_code}",
            "query": query,
            "total_results": 0,
            "results": [],
        }

    parsed = _extract_assistant_json(r.json())
    if parsed is None:
        logger.error("pi-coder search returned no parseable JSON message")
        return {
            "error": "no parseable JSON in response",
            "query": query,
            "total_results": 0,
            "results": [],
        }

    results = parsed.get("results") or []
    return {
        "query": parsed.get("query", query),
        "total_results": len(results),
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", r.get("snippet", "")),
            }
            for r in results
        ],
    }
