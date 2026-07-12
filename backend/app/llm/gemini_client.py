"""Gemini free-tier client — a third LLM fallback beyond FluffyJaws and Groq.

Groq's free tier has a small fixed daily token cap (100k/day) that a single
real BRD analysis can consume most of. Gemini's free tier is far less
restrictive, so this is what keeps the pipeline usable once Groq's daily
budget is exhausted — which happens easily under real testing/demo load.
"""

import asyncio

import httpx

from app.config import settings

_CONCURRENCY_LIMIT = asyncio.Semaphore(2)
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _build_body(prompt: str, system: str | None) -> dict:
    body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


def _extract_text(data: dict) -> str:
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def call_gemini(prompt: str, system: str | None = None, retries: int = 2) -> str:
    async with _CONCURRENCY_LIMIT:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{_BASE_URL}/{settings.gemini_model}:generateContent",
                        params={"key": settings.gemini_api_key},
                        json=_build_body(prompt, system),
                    )
                resp.raise_for_status()
                return _extract_text(resp.json())
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))
        raise last_error


async def stream_gemini(prompt: str, system: str | None = None):
    """Yields text chunks from Gemini's SSE streaming endpoint."""
    async with _CONCURRENCY_LIMIT:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{_BASE_URL}/{settings.gemini_model}:streamGenerateContent",
                params={"key": settings.gemini_api_key, "alt": "sse"},
                json=_build_body(prompt, system),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    import json
                    payload = json.loads(line[len("data: "):])
                    candidates = payload.get("candidates") or []
                    if not candidates:
                        continue
                    for part in candidates[0].get("content", {}).get("parts", []):
                        text = part.get("text")
                        if text:
                            yield text
