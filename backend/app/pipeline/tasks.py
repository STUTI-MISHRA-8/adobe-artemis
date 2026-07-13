"""Pass 3 — decompose requirements into a phased AEP execution plan.

Schema before Dataset, Dataset before Ingestion, Ingestion before Activation.
Requirements are batched and decomposed concurrently, then every task is
grouped into one of the four AEP build phases for the execution-plan board.
"""

import asyncio
import json

from app.config import settings
from app.llm.router import call_llm_json
from app.models import Task
from app.pipeline.sanitize import sanitize_layer, sanitize_priority

_DEFAULT_CONCURRENCY = max(6, len(settings.groq_api_key_list))
_STAGGER_DELAY_S = 0.35

SYSTEM_PROMPT = """You are a senior AEP implementation architect. Schema before Dataset, Dataset before Ingestion, Ingestion before Activation.
You always respond with valid JSON only — no explanation, no markdown, no preamble."""

BATCH_SIZE = 12

_PHASE_FALLBACK = {
    "schema": 1,
    "dataset": 2,
    "ingestion": 3,
    "modeling": 3,
    "activation": 4,
    "governance": 4,
    "reporting": 4,
    "general": 4,
}


def _build_prompt(batch: list) -> str:
    req_text = json.dumps(batch, indent=1)
    return f"""Here are {len(batch)} AEP implementation requirements:

{req_text}

Create an AEP execution plan. For each requirement create one or more concrete tasks.

OUTPUT RULES — CRITICAL:
- Respond with ONLY a raw JSON array
- NO markdown, NO headers, NO explanation
- Your entire response must start with [ and end with ]

Each task object must have exactly:
- "req_id": the requirement ID this implements
- "title": action title max 80 chars starting with a verb
- "description": one technical sentence
- "aep_layer": one of schema, dataset, ingestion, modeling, activation, governance, reporting, general
- "priority": one of high, medium, low
- "phase": 1 for schema, 2 for dataset, 3 for ingestion, 4 for activation (governance/reporting tasks also go in the phase where they're actually executed)
- "source_section": copy from the requirement
- "acceptance_criteria": one sentence verification

Return the JSON array only."""


async def decompose_batch(batch: list, semaphore: asyncio.Semaphore) -> list:
    async with semaphore:
        try:
            data, _provider = await call_llm_json(_build_prompt(batch), system=SYSTEM_PROMPT)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Task decomposition batch failed: {e}")
            return []


async def run_pass3(requirements: list, max_concurrency: int = _DEFAULT_CONCURRENCY, on_progress=None) -> dict:
    if not requirements:
        return {"phase_1_schema": [], "phase_2_dataset": [], "phase_3_ingestion": [], "phase_4_activation": [], "total_tasks": 0}

    slim_reqs = [
        {
            "req_id": r.get("req_id"),
            "aep_layer": r.get("aep_layer"),
            "priority": r.get("priority"),
            "description": r.get("description"),
            "source_section": r.get("source_section"),
        }
        for r in requirements
    ]
    batches = [slim_reqs[i:i + BATCH_SIZE] for i in range(0, len(slim_reqs), BATCH_SIZE)]
    semaphore = asyncio.Semaphore(max_concurrency)
    completed = 0

    async def worker(index: int, batch: list):
        nonlocal completed
        await asyncio.sleep(index * _STAGGER_DELAY_S)
        result = await decompose_batch(batch, semaphore)
        completed += 1
        if on_progress:
            await on_progress(completed, len(batches), len(result))
        return result

    batch_results = await asyncio.gather(*(worker(i, b) for i, b in enumerate(batches)))
    all_tasks = [t for batch_result in batch_results for t in batch_result]

    validated_tasks = []
    for i, task in enumerate(all_tasks):
        task["task_id"] = f"T-{i + 1:03d}"
        task["aep_layer"] = sanitize_layer(task.get("aep_layer"))
        task["priority"] = sanitize_priority(task.get("priority"))
        task.setdefault("dependencies", [])
        phase = task.get("phase")
        if phase not in (1, 2, 3, 4):
            task["phase"] = _PHASE_FALLBACK.get(task["aep_layer"], 4)
        try:
            validated_tasks.append(Task(**task).model_dump())
        except Exception as e:
            print(f"Skipping invalid task (missing required field): {e}")

    phases: dict[int, list] = {1: [], 2: [], 3: [], 4: []}
    for task in validated_tasks:
        phases[task["phase"]].append(task)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    for phase in phases:
        phases[phase].sort(key=lambda t: priority_order.get(t.get("priority", "low"), 2))

    return {
        "phase_1_schema": phases[1],
        "phase_2_dataset": phases[2],
        "phase_3_ingestion": phases[3],
        "phase_4_activation": phases[4],
        "total_tasks": len(validated_tasks),
    }
