"""Thin client for actually executing a generated wizard-step payload against
a real Adobe Experience Platform sandbox.

Deliberately minimal: one OAuth Server-to-Server token exchange (cached until
near expiry), a best-effort tenant ID lookup (some payloads reference it), and
a single generic call() that substitutes the same {PLACEHOLDER} tokens the
payload generator produces and fires the real request. No retries, no
fallback provider — if this fails, the caller should see the real AEP error,
not a masked one.
"""

import re
import time

import httpx

from app.config import settings

IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"

_token_cache: dict = {"token": None, "expires_at": 0.0}
_tenant_cache: dict = {"tenant_id": None, "fetched": False}

_PLACEHOLDER_RE = re.compile(r"\{([A-Z_]+)\}")


async def get_access_token() -> str:
    now = time.monotonic()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            IMS_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.aep_client_id,
                "client_secret": settings.aep_client_secret,
                "scope": settings.aep_scopes,
            },
        )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + body.get("expires_in", 3600) - 120
    return token


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": settings.aep_client_id,
        "x-gw-ims-org-id": settings.aep_org_id,
    }


async def get_tenant_id() -> str | None:
    """Best-effort — not every org exposes this, and not every payload needs it."""
    if _tenant_cache["fetched"]:
        return _tenant_cache["tenant_id"]
    _tenant_cache["fetched"] = True
    try:
        token = await get_access_token()
        headers = {**_auth_headers(token), "x-sandbox-name": settings.aep_sandbox_name}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://platform.adobe.io/data/foundation/schemaregistry/global/tenant",
                headers=headers,
            )
        if resp.status_code == 200:
            _tenant_cache["tenant_id"] = resp.json().get("tenantId")
    except Exception:
        pass
    return _tenant_cache["tenant_id"]


def _substitute(value, mapping: dict[str, str]):
    if isinstance(value, str):
        return _PLACEHOLDER_RE.sub(lambda m: mapping.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _substitute(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, mapping) for v in value]
    return value


async def execute_payload(method: str, endpoint: str, headers: dict, body) -> dict:
    if not settings.aep_configured:
        raise RuntimeError("AEP sandbox is not configured (missing credentials or sandbox name)")

    token = await get_access_token()
    tenant_id = await get_tenant_id()
    mapping = {
        "ACCESS_TOKEN": token,
        "API_KEY": settings.aep_client_id,
        "IMS_ORG_ID": settings.aep_org_id,
        "SANDBOX_NAME": settings.aep_sandbox_name,
        "TENANT_ID": tenant_id or "{TENANT_ID}",
    }

    real_endpoint = _substitute(endpoint, mapping)
    real_headers = _substitute(headers, mapping)
    real_body = _substitute(body, mapping) if body is not None else None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, real_endpoint, headers=real_headers, json=real_body)

    try:
        parsed = resp.json()
    except ValueError:
        parsed = resp.text

    return {
        "status_code": resp.status_code,
        "ok": 200 <= resp.status_code < 300,
        "response": parsed,
        "endpoint": real_endpoint,
    }
