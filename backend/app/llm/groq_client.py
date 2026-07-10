"""Groq free-tier client — safety-net fallback so LLM calls never cost money.

Groq's free tier has a tight tokens-per-minute cap, and it's easy to blow
through it when several sections fall back from FluffyJaws at once. Rather
than letting a 429 kill the whole section, we back off and retry a few
times — the TPM window resets within seconds.
"""

import asyncio
import re
import threading

from groq import Groq, RateLimitError

from app.config import settings

_client: Groq | None = None
_CONCURRENCY_LIMIT = asyncio.Semaphore(2)
_RETRY_WAIT_RE = re.compile(r"try again in ([\d.]+)s")


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _sync_call(prompt: str, system: str | None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0,
        max_tokens=4096,
    )
    return response.choices[0].message.content


async def call_groq(prompt: str, system: str | None = None, retries: int = 3) -> str:
    async with _CONCURRENCY_LIMIT:
        for attempt in range(retries):
            try:
                return await asyncio.to_thread(_sync_call, prompt, system)
            except RateLimitError as e:
                if attempt == retries - 1:
                    raise
                match = _RETRY_WAIT_RE.search(str(e))
                wait = float(match.group(1)) + 0.5 if match else 5.0 * (attempt + 1)
                await asyncio.sleep(wait)
        raise RuntimeError("unreachable")


async def stream_groq(prompt: str, system: str | None = None):
    """Yields text chunks from a real Groq streaming completion, bridged from its sync SDK via a thread."""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer():
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            stream = _get_client().chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                temperature=0,
                max_tokens=4096,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", delta))
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", e))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    async with _CONCURRENCY_LIMIT:
        threading.Thread(target=producer, daemon=True).start()
        while True:
            kind, value = await queue.get()
            if kind == "chunk":
                yield value
            elif kind == "error":
                raise value
            else:
                break
