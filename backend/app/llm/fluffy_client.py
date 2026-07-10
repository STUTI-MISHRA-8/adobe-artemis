"""Adobe FluffyJaws client.

FluffyJaws' Okta org enforces private_key_jwt for client_credentials grants,
so the client_id/secret pair alone cannot mint a server-to-server token. The
supported integration path on this machine is the `fj` CLI, which already
holds a valid browser-login session (`fj whoami` confirms it) and handles
Okta token refresh internally. We shell out to it, piping the prompt over
stdin so long prompts never hit a command-line length limit.
"""

import asyncio
import codecs
import shutil
from pathlib import Path

from app.config import settings

_DEFAULT_FJ_PATH = Path.home() / "AppData" / "Local" / "fj" / "bin" / "fj.cmd"

# The fj CLI spawns a Node process per call and gets unreliable (silent empty
# output) under high concurrency. This caps concurrent `fj` invocations
# regardless of how many pipeline passes are calling in parallel.
_FJ_CONCURRENCY_LIMIT = asyncio.Semaphore(3)


def _resolve_fj_path() -> str:
    which_result = shutil.which("fj")
    if which_result:
        return which_result
    if _DEFAULT_FJ_PATH.exists():
        return str(_DEFAULT_FJ_PATH)
    raise FileNotFoundError("fj CLI not found on PATH or at the default install location")


def _fj_args(fast: bool) -> list[str]:
    args = ["chat", "--api", settings.fluffyjaws_api_host, "--model", settings.fluffyjaws_model]
    if fast:
        args.append("--fast")
    return args


async def call_fluffy(prompt: str, system: str | None = None, timeout: float = 120.0, fast: bool = False) -> str:
    """Runs `fj chat` with the prompt piped over stdin, returns raw stdout text.

    `fast` trades reasoning depth for speed (`fj`'s "thinking" mode is the
    default and can take 30-90s+ on non-trivial prompts) — worth it for
    mechanical/procedural output where depth matters less than latency.
    """
    fj_path = _resolve_fj_path()
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    async with _FJ_CONCURRENCY_LIMIT:
        process = await asyncio.create_subprocess_exec(
            fj_path, *_fj_args(fast),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=full_prompt.encode("utf-8")),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError("fj CLI call timed out")

    if process.returncode != 0:
        raise RuntimeError(f"fj CLI exited {process.returncode}: {stderr.decode(errors='replace')[:500]}")

    output = stdout.decode(errors="replace").strip()
    if not output:
        raise RuntimeError(f"fj CLI returned empty output (stderr: {stderr.decode(errors='replace')[:300]})")

    return output


async def stream_fluffy(prompt: str, system: str | None = None, timeout: float = 120.0, fast: bool = False):
    """Yields decoded text chunks as `fj chat` writes them to stdout in real time."""
    fj_path = _resolve_fj_path()
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    async with _FJ_CONCURRENCY_LIMIT:
        process = await asyncio.create_subprocess_exec(
            fj_path, *_fj_args(fast),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        process.stdin.write(full_prompt.encode("utf-8"))
        process.stdin.close()

        got_output = False
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                chunk = await asyncio.wait_for(process.stdout.read(256), timeout=timeout)
                if not chunk:
                    break
                got_output = True
                text = decoder.decode(chunk)
                if text:
                    yield text
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError("fj CLI stream timed out")

        tail = decoder.decode(b"", final=True)
        if tail:
            yield tail

        await process.wait()
        if process.returncode != 0 and not got_output:
            stderr = await process.stderr.read()
            raise RuntimeError(f"fj CLI exited {process.returncode}: {stderr.decode(errors='replace')[:500]}")
        if not got_output:
            raise RuntimeError("fj CLI returned empty output")
