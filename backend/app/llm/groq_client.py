"""Groq free-tier client — safety-net fallback so LLM calls never cost money.

Groq's free tier has a tight tokens-per-day cap that a single real BRD
analysis can consume most of. Rather than a single key, this rotates across
however many keys are configured — each on a separate Groq organization has
its own independent daily quota. A key found exhausted for the day is
skipped for all future calls (not just retried within one call), so the
system doesn't waste time rediscovering the same dead key over and over.

Concurrency scales with the number of configured keys: each concurrent call
is assigned a different starting key round-robin, so N keys genuinely means
N calls in flight at once against N separate quotas — not N keys sitting
idle behind one shared low concurrency limit.
"""

import asyncio
import re
import threading
import time

from groq import Groq, RateLimitError

from app.config import settings

_RETRY_WAIT_RE = re.compile(r"try again in ([\d.]+)s")
_DAILY_EXHAUSTION_THRESHOLD_S = 30.0  # a wait longer than this means "done for today", not a short burst
_DEFAULT_COOLDOWN_S = 3600.0  # fallback cooldown when Groq doesn't report a wait time

_clients: dict[str, Groq] = {}
_dead_until: dict[str, float] = {}  # key -> monotonic time after which it's worth retrying again
_lock = threading.Lock()
_current_index = 0
_CONCURRENCY_LIMIT = asyncio.Semaphore(max(2, len(settings.groq_api_key_list)))


def _get_client(key: str) -> Groq:
    if key not in _clients:
        _clients[key] = Groq(api_key=key)
    return _clients[key]


def _is_dead(key: str) -> bool:
    expiry = _dead_until.get(key)
    return expiry is not None and time.monotonic() < expiry


def _mark_dead(key: str, cooldown_s: float | None) -> None:
    _dead_until[key] = time.monotonic() + (cooldown_s if cooldown_s else _DEFAULT_COOLDOWN_S)


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


def _claim_start_index(keys: list[str]) -> int:
    """Atomically claims the next round-robin starting key. Called once per
    invocation (not per retry) so concurrent calls spread across different
    keys immediately, before any of them have made a network call."""
    global _current_index
    with _lock:
        start = _current_index % len(keys)
        _current_index += 1
    return start


async def call_groq(prompt: str, system: str | None = None, retries: int = 3) -> str:
    async with _CONCURRENCY_LIMIT:
        keys = _live_keys()
        start = _claim_start_index(keys)

        last_error: Exception | None = None
        for offset in range(len(keys)):
            idx = (start + offset) % len(keys)
            key = keys[idx]
            if _is_dead(key):
                continue

            for attempt in range(retries):
                try:
                    return await asyncio.to_thread(_sync_call, prompt, system, key)
                except RateLimitError as e:
                    last_error = e
                    wait = _wait_seconds(e)
                    if wait is not None and wait > _DAILY_EXHAUSTION_THRESHOLD_S:
                        print(f"Groq key ...{key[-6:]} exhausted — cooling down for {wait:.0f}s, rotating to next key")
                        _mark_dead(key, wait)
                        break  # move to next key immediately, don't waste retries on a dead key
                    if attempt < retries - 1:
                        await asyncio.sleep((wait + 0.5) if wait else 5.0 * (attempt + 1))
                except Exception as e:
                    # Anything else (bad/invalid key, network hiccup, etc.) shouldn't kill the
                    # whole rotation — one broken key must never block the others from working.
                    last_error = e
                    print(f"Groq key ...{key[-6:]} failed with {type(e).__name__}: {e} — rotating to next key")
                    _mark_dead(key, None)
                    break

        raise last_error or RuntimeError("All configured Groq keys are currently rate-limited or exhausted")


async def stream_groq(prompt: str, system: str | None = None):
    """Yields text chunks from a real Groq streaming completion, bridged from its sync SDK via a thread.
    Claims its own round-robin key like call_groq — streaming failures fall through to the caller
    (router.py), which moves on to the next provider rather than rotating keys mid-stream."""
    keys = _live_keys()
    start = _claim_start_index(keys)
    key = next((keys[(start + offset) % len(keys)] for offset in range(len(keys))
                if not _is_dead(keys[(start + offset) % len(keys)])), keys[start])

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
