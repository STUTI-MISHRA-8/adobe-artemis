"""Guided implementation wizard — turns the flat task list into an ordered,
step-by-step build sequence with on-demand, per-step how-to guidance.

Ordering is a cheap, honest heuristic rather than a fabricated dependency
graph: phase order (schema -> dataset -> ingestion -> activation) is the real
sequence AEP recommends, priority breaks ties within a phase. It's a
suggestion, not a gate — a real team works phases in parallel, so every step
stays interactive regardless of what earlier phases have finished.
"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import db
from app.aep import client as aep_client
from app.aep.simulate import simulate_response
from app.config import settings
from app.llm.router import call_llm_json, stream_llm

router = APIRouter()

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

HOWTO_SYSTEM_PROMPT = """You are a Principal Adobe Experience Platform Solution Architect walking a junior implementation engineer through exactly how to execute one specific task inside the real Adobe Experience Platform UI.
Be concrete and click-by-click: name real AEP screens (Schema Editor, Dataset creation wizard, Source Connectors, Segment Builder, Destinations, Data Governance labels, etc.), real actions (e.g. "click Add Field Group", "select Adobe Analytics Data Connector as the source"), and call out settings/values to use based on the task's details.
Format as a numbered list of concrete steps. End with one line starting with "Verify:" describing how to confirm it worked.
Keep it tight — 5-10 steps. No preamble, no markdown headers, just the numbered list."""

PAYLOAD_SYSTEM_PROMPT = """You are an Adobe Experience Platform integration engineer. Given one implementation task, produce the exact REST API call an engineer would run against the real AEP APIs (Schema Registry, Catalog Service, Flow Service, Segmentation Service, or Destinations/Data Governance) to accomplish it.

Rules:
- Pick the single real AEP API that best matches the task's AEP layer (schema -> Schema Registry API, dataset -> Catalog Service API, ingestion -> Flow Service API, activation -> Segmentation Service API or Destinations API, governance -> Data Governance/Policy Service API).
- Use the task's title/description/acceptance criteria and any source quotes to make the JSON body concrete and realistic (real-looking field names, XDM types, dataset names) — never a generic placeholder body like {"example": true}.
- Use placeholder tokens exactly as written for anything environment-specific: {IMS_ORG_ID}, {SANDBOX_NAME}, {ACCESS_TOKEN}, {API_KEY}, {TENANT_ID}. Never invent a fake real-looking org ID or credential.
- Respond with ONLY strict JSON (no markdown fences, no prose) matching this exact shape:
{
  "api_name": "string — e.g. Schema Registry API",
  "method": "GET|POST|PUT|PATCH|DELETE",
  "endpoint": "https://platform.adobe.io/... full path with {SANDBOX_NAME}-style placeholders where needed",
  "headers": {"Authorization": "Bearer {ACCESS_TOKEN}", "x-api-key": "{API_KEY}", "x-gw-ims-org-id": "{IMS_ORG_ID}", "x-sandbox-name": "{SANDBOX_NAME}", "Content-Type": "application/json"},
  "body": { ...the actual realistic JSON request body, or null for GET... },
  "notes": "1-2 sentences: any prerequisite or what to check after running this"
}"""


def _ordered_steps(result: dict) -> list[dict]:
    tasks = result["tasks"]
    return sorted(tasks, key=lambda t: (t["phase"], PRIORITY_RANK.get(t["priority"], 2), t["req_id"], t["task_id"]))


def _build_wizard_state(result: dict, progress: dict[str, str], assignments: dict[str, str] | None = None) -> dict:
    assignments = assignments or {}
    ordered = _ordered_steps(result)
    total = len(ordered)
    done_count = 0
    current_found = False
    steps = []

    for task in ordered:
        status = progress.get(task["task_id"], "pending")
        is_done = status == "done"
        if is_done:
            done_count += 1
        # Phase order (schema -> dataset -> ingestion -> activation) is a
        # recommended sequence, not a hard gate — a team works these in
        # parallel in practice, so every step stays open regardless of what
        # earlier phases have finished. "is_current" still flags the next
        # suggested step in priority order, it just no longer blocks anything.
        is_ready = True
        is_current = not is_done and not current_found
        if is_current:
            current_found = True
        steps.append({
            **task,
            "status": status,
            "is_ready": is_ready,
            "is_current": is_current,
            "assigned_to": assignments.get(task["task_id"]),
        })

    return {
        "steps": steps,
        "total": total,
        "done": done_count,
        "percent_complete": round(done_count / total * 100, 1) if total else 100.0,
    }


@router.get("/api/jobs/{job_id}/wizard")
async def get_wizard(job_id: str):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")
    progress = db.get_task_progress(job_id)
    assignments = db.get_task_assignments(job_id)
    return _build_wizard_state(job["result"], progress, assignments)


class StatusUpdate(BaseModel):
    status: str


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/status")
async def update_task_status(job_id: str, task_id: str, body: StatusUpdate):
    if body.status not in ("done", "pending"):
        raise HTTPException(400, "status must be 'done' or 'pending'")
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")
    db.set_task_status(job_id, task_id, body.status)
    progress = db.get_task_progress(job_id)
    assignments = db.get_task_assignments(job_id)
    return _build_wizard_state(job["result"], progress, assignments)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _task_context(result: dict, task_id: str) -> tuple[dict, str, list[str]]:
    task = next((t for t in result["tasks"] if t["task_id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    trace_node = next((n for n in result.get("trace", []) if n["req_id"] == task["req_id"]), None)
    requirement_desc = trace_node["description"] if trace_node else ""
    source_quotes = [
        obs["verbatim_quote"] or obs["text"] for obs in (trace_node["observations"] if trace_node else [])
    ][:3]
    return task, requirement_desc, source_quotes


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/howto")
async def get_task_howto(job_id: str, task_id: str):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    cached = db.get_task_howto(job_id, task_id)
    if cached:
        async def cached_stream():
            yield _sse("chunk", {"text": cached})
            yield _sse("done", {"content": cached, "cached": True})
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    task, requirement_desc, source_quotes = _task_context(job["result"], task_id)

    prompt = f"""TASK: {task['title']}
DESCRIPTION: {task['description']}
AEP LAYER: {task['aep_layer']}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria', '')}

PARENT REQUIREMENT: {requirement_desc}

SOURCE CONTEXT FROM THE DOCUMENT:
{chr(10).join(f'- "{q}"' for q in source_quotes) if source_quotes else "(none)"}

Write the click-by-click AEP walkthrough for this exact task."""

    async def generate_stream():
        full_text = ""
        async for chunk, _provider in stream_llm(prompt, system=HOWTO_SYSTEM_PROMPT, fast=True):
            full_text += chunk
            yield _sse("chunk", {"text": chunk})
        db.save_task_howto(job_id, task_id, full_text.strip())
        yield _sse("done", {"content": full_text.strip(), "cached": False})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


async def _get_or_generate_payload(job: dict, job_id: str, task_id: str) -> dict:
    cached = db.get_task_payload(job_id, task_id)
    if cached:
        return cached

    task, requirement_desc, source_quotes = _task_context(job["result"], task_id)

    prompt = f"""TASK: {task['title']}
DESCRIPTION: {task['description']}
AEP LAYER: {task['aep_layer']}
ACCEPTANCE CRITERIA: {task.get('acceptance_criteria', '')}

PARENT REQUIREMENT: {requirement_desc}

SOURCE CONTEXT FROM THE DOCUMENT:
{chr(10).join(f'- "{q}"' for q in source_quotes) if source_quotes else "(none)"}

Produce the ready-to-run AEP API call JSON for this exact task."""

    payload, _provider = await call_llm_json(prompt, system=PAYLOAD_SYSTEM_PROMPT, fast=True)
    db.save_task_payload(job_id, task_id, payload)
    return payload


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/payload")
async def get_task_payload(job_id: str, task_id: str):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    cached = db.get_task_payload(job_id, task_id)
    payload = await _get_or_generate_payload(job, job_id, task_id)
    last_execution = db.get_task_execution(job_id, task_id)
    return {**payload, "cached": cached is not None, "last_execution": last_execution}


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/execute")
async def execute_task(job_id: str, task_id: str):
    if not settings.aep_configured:
        raise HTTPException(400, "AEP sandbox is not configured. Add AEP credentials to backend/.env first.")

    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    payload = await _get_or_generate_payload(job, job_id, task_id)

    try:
        result = await aep_client.execute_payload(
            payload["method"], payload["endpoint"], payload["headers"], payload.get("body")
        )
        saved = db.save_task_execution(
            job_id, task_id, result["ok"], result["status_code"], result["response"], result["endpoint"]
        )
    except Exception as e:
        saved = db.save_task_execution(job_id, task_id, False, None, None, payload.get("endpoint"), error=str(e))
        return saved

    if result["ok"]:
        db.set_task_status(job_id, task_id, "done")

    return saved


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/simulate")
async def simulate_task(job_id: str, task_id: str):
    """Demo path: synthesizes a realistic-shaped AEP success response without
    ever making a network call, so the wizard's execute flow can be shown
    end-to-end without needing sandbox credentials or permissions. Always
    marked simulated=true so it's never mistaken for a real deployment."""
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    payload = await _get_or_generate_payload(job, job_id, task_id)
    task, _requirement_desc, _source_quotes = _task_context(job["result"], task_id)
    result = simulate_response(payload, task)
    saved = db.save_task_execution(
        job_id, task_id, result["ok"], result["status_code"], result["response"], result["endpoint"],
        simulated=True,
    )
    db.set_task_status(job_id, task_id, "done")
    return saved
