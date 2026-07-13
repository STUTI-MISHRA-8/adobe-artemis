"""Pass 2 — structure raw observations into formal AEP requirements.

Batches observations (so prompts stay small and fast), structures each
batch concurrently, then runs a coverage audit. Any observation that no
requirement ends up covering is NOT silently dropped — it's captured into
an explicit "unclassified" requirement so the product can honestly claim
zero requirements are ever lost.
"""

import asyncio
import json

from app.config import settings
from app.llm.router import call_llm_json
from app.models import Requirement
from app.pipeline.sanitize import sanitize_flags, sanitize_layer, sanitize_priority

_DEFAULT_CONCURRENCY = max(6, len(settings.groq_api_key_list))

SYSTEM_PROMPT = """You are a Principal Adobe Experience Platform Solution Architect.
You turn raw observations into formal, actionable AEP implementation requirements.
You never lose a real requirement. You use precise AEP terminology.
You always respond with valid JSON only — no explanation, no markdown, no preamble."""

BATCH_SIZE = 10


def _build_prompt(batch: list) -> str:
    obs_text = json.dumps(batch, indent=2)
    return f"""Turn these observations into formal AEP implementation requirements.

OBSERVATIONS:
{obs_text}

RULES:
1. Every obs_id MUST appear in at least one requirement's source_obs. Lose nothing.
2. Group observations that describe the same technical work into one requirement. Keep distinct concerns separate.
3. Use precise AEP terminology: XDM schemas, identity namespaces, datasets, source connectors (S3, Redshift, Analytics Data Connector), dataflows, data mapping, segments, merge policies, destinations, DULE policies, Adobe Mix Modeler models, CJA.
4. Preserve specific details exactly — technology names, numeric thresholds, timelines, channel names.
5. Priority: high = blocks other work or is core to the deliverable, medium = standard, low = nice to have.

Each requirement must have:
- "aep_layer": one of "schema", "dataset", "ingestion", "modeling", "activation", "governance", "reporting", "general"
- "priority": one of "high", "medium", "low"
- "description": precise, actionable, technical, max 400 chars, start with a verb
- "source_obs": list of ALL obs_ids this covers
- "source_section": section title
- "sec_id": section ID
- "flags": list from "clear", "implicit", "ambiguous", "contradiction", "assumption"
- "dependencies": []

Return JSON array only. No markdown. No other text."""


async def structure_batch(batch: list, semaphore: asyncio.Semaphore) -> tuple[list, str | None]:
    """Returns (requirements, error). error is None on success — including a
    legitimate "the LLM found zero requirements in this batch" — and is set
    only when the underlying call itself failed (quota exhaustion, timeout,
    unparseable response), so the caller can tell those two cases apart."""
    async with semaphore:
        try:
            data, _provider = await call_llm_json(_build_prompt(batch), system=SYSTEM_PROMPT)
            return (data if isinstance(data, list) else []), None
        except Exception as e:
            print(f"Requirement batch structuring failed: {e}")
            return [], str(e)


async def run_pass2(observations: list, max_concurrency: int = _DEFAULT_CONCURRENCY, on_progress=None) -> list:
    if not observations:
        return []

    batches = [observations[i:i + BATCH_SIZE] for i in range(0, len(observations), BATCH_SIZE)]
    semaphore = asyncio.Semaphore(max_concurrency)
    completed = 0

    async def worker(batch):
        nonlocal completed
        result, error = await structure_batch(batch, semaphore)
        completed += 1
        if on_progress:
            await on_progress(completed, len(batches), len(result))
        return result, error

    batch_results = await asyncio.gather(*(worker(b) for b in batches))

    failures = [err for _, err in batch_results if err is not None]
    if failures and len(failures) == len(batch_results):
        raise RuntimeError(
            f"Requirement structuring failed for all {len(batch_results)} batch(es) — "
            f"the underlying LLM call never succeeded. Last error: {failures[-1]}"
        )

    all_raw = [req for batch_result, _ in batch_results for req in batch_result]

    validated = []
    next_id = 1
    for req in all_raw:
        # Assign the id from a counter that only advances on success — using the
        # raw list index here instead would leave gaps whenever an item fails
        # validation, and a later step (_capture_orphans) that sizes its own
        # numbering off len(requirements) would then collide with an id whose
        # number was already used by a higher, still-valid, index.
        req["req_id"] = f"R-{next_id:03d}"
        req["aep_layer"] = sanitize_layer(req.get("aep_layer"))
        req["priority"] = sanitize_priority(req.get("priority"))
        req["flags"] = sanitize_flags(req.get("flags"))
        req.setdefault("source_obs", [])
        req.setdefault("dependencies", [])
        try:
            requirement = Requirement(**req)
            validated.append(requirement.model_dump())
            next_id += 1
        except Exception as e:
            print(f"Skipping invalid requirement (missing required field): {e}")
            continue

    return _capture_orphans(observations, validated)


def _capture_orphans(observations: list, requirements: list) -> list:
    """Ensures every observation is covered — orphans become an explicit requirement instead of vanishing."""
    all_obs_by_id = {obs["obs_id"]: obs for obs in observations}
    mapped_ids = {oid for req in requirements for oid in req.get("source_obs", [])}
    orphan_ids = [oid for oid in all_obs_by_id if oid not in mapped_ids]

    if not orphan_ids:
        return requirements

    # Derived from the highest existing numeric id, not len(requirements) —
    # the two aren't guaranteed to match, and a mismatch here previously
    # produced duplicate req_ids (and duplicate React keys) downstream.
    existing_nums = [int(r["req_id"].split("-")[1]) for r in requirements if r["req_id"].startswith("R-")]
    next_num = max(existing_nums, default=0) + 1
    orphans_by_section: dict[str, list[str]] = {}
    for oid in orphan_ids:
        sec_id = all_obs_by_id[oid].get("sec_id", "S-000")
        orphans_by_section.setdefault(sec_id, []).append(oid)

    for sec_id, oids in orphans_by_section.items():
        sample = all_obs_by_id[oids[0]]
        requirements.append(Requirement(
            req_id=f"R-{next_num:03d}",
            aep_layer=sample.get("aep_relevance", "general"),
            priority="medium",
            description="Review and formally scope the following unclassified observations that did not "
                         "fit cleanly into another requirement — nothing from the source document is discarded.",
            source_obs=oids,
            source_section=sample.get("section_title", "Unknown"),
            sec_id=sec_id,
            flags=["unclassified"],
            dependencies=[],
        ).model_dump())
        next_num += 1

    return requirements


def run_coverage_audit(observations: list, requirements: list) -> dict:
    all_obs_ids = {obs["obs_id"] for obs in observations}
    mapped_ids = {oid for req in requirements for oid in req.get("source_obs", [])}
    orphaned = all_obs_ids - mapped_ids
    return {
        "total_observations": len(all_obs_ids),
        "mapped_observations": len(mapped_ids),
        "orphaned_observations": list(orphaned),
        "coverage_percent": round(len(mapped_ids) / len(all_obs_ids) * 100, 1) if all_obs_ids else 100.0,
    }
