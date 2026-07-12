"""Unified LLM entry point: FluffyJaws primary, Groq free-tier fallback.

Every call in the pipeline goes through call_llm() so there is exactly one
place that decides which provider to use and how to recover from failure —
this is what keeps the whole system at $0 cost with no single point of
failure.
"""

import asyncio
import json
import re

from app.llm.fluffy_client import call_fluffy, stream_fluffy
from app.llm.gemini_client import call_gemini, stream_gemini
from app.llm.groq_client import call_groq, stream_groq


def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not extract JSON from response: {text[:200]}")


async def call_llm(prompt: str, system: str | None = None, retries: int = 2, fast: bool = False) -> tuple[str, str]:
    """Returns (response_text, provider_used).

    `fast` skips Fluffy's "thinking" reasoning mode (30-90s+ per call) for
    output where mechanical correctness matters more than depth — also uses
    a shorter per-attempt timeout since fast calls that hang are more likely
    stuck than genuinely still reasoning.
    """
    last_error: Exception | None = None
    timeout = 45.0 if fast else 120.0

    for attempt in range(retries):
        try:
            text = await call_fluffy(prompt, system=system, timeout=timeout, fast=fast)
            if text and text.strip():
                return text, "fluffy"
        except Exception as e:
            last_error = e
            await asyncio.sleep(1.5 * (attempt + 1))

    try:
        text = await call_groq(prompt, system=system)
        return text, "groq"
    except Exception as groq_error:
        try:
            text = await call_gemini(prompt, system=system)
            return text, "gemini"
        except Exception as gemini_error:
            fluffy_desc = f"{type(last_error).__name__}: {last_error}" if last_error else "none"
            raise RuntimeError(
                f"FluffyJaws, Groq, and Gemini all failed. "
                f"Fluffy error: {fluffy_desc}. Groq error: {type(groq_error).__name__}: {groq_error}. "
                f"Gemini error: {type(gemini_error).__name__}: {gemini_error}"
            )


async def call_llm_json(prompt: str, system: str | None = None, fast: bool = False):
    text, provider = await call_llm(prompt, system=system, fast=fast)
    return extract_json(text), provider


async def stream_llm(prompt: str, system: str | None = None, fast: bool = False):
    """Yields (chunk, provider) tuples. Falls back to Groq only if Fluffy fails before producing any output."""
    produced = False
    timeout = 45.0 if fast else 120.0
    try:
        async for chunk in stream_fluffy(prompt, system=system, timeout=timeout, fast=fast):
            produced = True
            yield chunk, "fluffy"
        return
    except Exception:
        if produced:
            return  # partial stream already shown to the user — don't restart from scratch on a different provider

    try:
        async for chunk in stream_groq(prompt, system=system):
            produced = True
            yield chunk, "groq"
        return
    except Exception:
        if produced:
            return

    async for chunk in stream_gemini(prompt, system=system):
        yield chunk, "gemini"
