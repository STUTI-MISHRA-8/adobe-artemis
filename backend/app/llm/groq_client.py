"""Groq free-tier client — safety-net fallback so LLM calls never cost money.

Groq's free tier has a tight tokens-per-day cap that a single real BRD
analysis can consume most of. Rather than a single key, this rotates across
however many keys are configured — each on a separate Groq organization has
its own independent daily quota. A key found exhausted for the day is
skipped for all future calls (not just retried within one call), so the
system doesn't waste time rediscovering the same dead key over and over.
"""

import asyncio
import re
import threading

from groq import Groq, RateLimitError

from app.config import settings

_CONCURRENCY_LIMIT = asyncio.Semaphore(2)
_RETRY_WAIT_RE = re.compile(r"try again in ([\d.]+)s")
_DAILY_EXHAUSTION_THRESHOLD_S = 30.0  # a wait longer than this means "done for today", not a short burst

_clients: dict[str, Groq] = {}
_dead_keys: set[str] = set()  # keys confirmed exhausted for the day — skipped until process restart
_lock = threading.Lock()
_current_index = 0


def _get_client(key: str) -> Groq:
    if key not in _clients:
        _clients[key] = Groq(api_key=key)
    return _clients[key]


def _live_keys() -> list[str]:
    keys = settings.groq_api_key_list
    if not keys:
        raise RuntimeError("No Groq API keys configured")
    return keys


def _sync_call(prompt: str, system: str | None, key: str) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _get_client(key).chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _wait_seconds(e: RateLimitError) -> float | None:
    match = _RETRY_WAIT_RE.search(str(e))
    return float(match.group(1)) if match else None


async def call_groq(prompt: str, system: str | None = None, retries: int = 3) -> str:
    global _current_index
    async with _CONCURRENCY_LIMIT:
        keys = _live_keys()
        with _lock:
            start = _current_index % len(keys)

        last_error: Exception | None = None
        for offset in range(len(keys)):
            idx = (start + offset) % len(keys)
            key = keys[idx]
            if key in _dead_keys:
                continue

            for attempt in range(retries):
                try:
                    result = await asyncio.to_thread(_sync_call, prompt, system, key)
                    with _lock:
                        _current_index = idx  # stick with a working key for subsequent calls
                    return result
                except RateLimitError as e:
                    last_error = e
                    wait = _wait_seconds(e)
                    if wait is not None and wait > _DAILY_EXHAUSTION_THRESHOLD_S:
                        print(f"Groq key ...{key[-6:]} exhausted for the day — rotating to next key")
                        _dead_keys.add(key)
                        break  # move to next key immediately, don't waste retries on a dead key
                    if attempt < retries - 1:
                        await asyncio.sleep((wait + 0.5) if wait else 5.0 * (attempt + 1))
                except Exception as e:
                    # Anything else (bad/invalid key, network hiccup, etc.) shouldn't kill the
                    # whole rotation — one broken key must never block the others from working.
                    last_error = e
                    print(f"Groq key ...{key[-6:]} failed with {type(e).__name__}: {e} — rotating to next key")
                    _dead_keys.add(key)
                    break

        raise last_error or RuntimeError("All configured Groq keys are exhausted for today")


async def stream_groq(prompt: str, system: str | None = None):
    """Yields text chunks from a real Groq streaming completion, bridged from its sync SDK via a thread.
    Uses whichever key call_groq last found working — streaming failures fall through to the caller
    (router.py), which moves on to the next provider rather than rotating keys mid-stream."""
    keys = _live_keys()
    with _lock:
        key = keys[_current_index % len(keys)]
        if key in _dead_keys:
            key = next((k for k in keys if k not in _dead_keys), key)

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer():
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            stream = _get_client(key).chat.completions.create(
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
