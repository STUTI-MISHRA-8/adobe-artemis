"""Deterministic, instant, clearly-labeled simulation of an AEP API call.

Used so the wizard can demo end-to-end "execute this step" completion without
real sandbox credentials or permissions. Never makes a network call — the
response is synthesized to match the real shape of each AEP API's success
response (schema $id, dataset path, segment id, etc.), but every identifier
in it is fabricated. Every caller of this must surface that clearly; nothing
here should ever be presented as a real AEP result.
"""

import time
import uuid


def _fake_id() -> str:
    return uuid.uuid4().hex


def simulate_response(payload: dict, task: dict | None = None) -> dict:
    api_name = (payload.get("api_name") or "").lower()
    body = payload.get("body") or {}
    task_title = (task or {}).get("title", "")

    if "schema registry" in api_name:
        response = {
            "$id": f"https://ns.adobe.com/{{IMS_ORG_ID}}/schemas/{_fake_id()}",
            "meta:altId": f"_{{TENANT_ID}}.schemas.{_fake_id()[:8]}",
            "version": "1.0.0",
            "title": body.get("title") or body.get("outputSchema") or task_title or "New Schema",
            "meta:status": "PUBLISHED",
        }
    elif "catalog" in api_name:
        response = [f"@/dataSets/{_fake_id()}"]
    elif "flow" in api_name:
        response = {"id": _fake_id(), "etag": '"0"', "status": "success"}
    elif "segmentation" in api_name:
        response = {
            "id": _fake_id(),
            "name": body.get("name") or task_title or "New Segment",
            "state": "ENABLED",
            "createTime": int(time.time()),
        }
    elif "destination" in api_name:
        response = {"id": _fake_id(), "status": "ENABLED"}
    else:
        response = {"id": _fake_id(), "status": "created"}

    return {
        "status_code": 201,
        "ok": True,
        "response": response,
        "endpoint": payload.get("endpoint"),
    }
