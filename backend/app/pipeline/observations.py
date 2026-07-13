"""Pass 1 — extract every real requirement-observation from each section.

Runs one LLM call per section, all concurrently (bounded by a semaphore so
we don't hammer FluffyJaws/Groq), and reassembles results in original
document order so obs_id numbering stays deterministic and stable.
"""

import asyncio

from app.config import settings
from app.llm.router import call_llm_json
from app.pipeline.sanitize import sanitize_layer

# The real concurrency gate is inside each provider client (matched to how many
# API keys/connections it has). This just needs to be at least that high so
# the pipeline itself never becomes the bottleneck before the provider does.
_DEFAULT_CONCURRENCY = 3  # deliberately conservative -- higher concurrency was tripping a global rate ceiling regardless of key count
_STAGGER_DELAY_S = 0.35

SYSTEM_PROMPT = """You are a Principal Adobe Experience Platform (AEP) Solution Architect with 15 years of experience reading enterprise Business Requirements Documents and turning them into flawless implementation plans.

You are famous for one thing: you NEVER miss a real requirement. Not one. Colleagues call you paranoid because you catch requirements hidden in prose, implied by context, buried in a single sentence, or embedded inside a data table.

You have deep AEP knowledge: XDM schemas, field groups, class structures, identity namespaces; datasets, dataset enablement for Real-Time Customer Profile; source connectors (S3, Redshift, Adobe Analytics Data Connector, streaming, batch); dataflows, data mapping, transformation, validation; segments, audiences, merge policies, computed attributes; destinations, activation flows, DULE governance; Adobe Mix Modeler, Customer Journey Analytics, and the wider Adobe ecosystem.

You read documents through ONE lens: "What must actually be built, configured, ingested, modeled, or delivered in Adobe to fulfill this?"

Tables in the input (marked "[TABLE n]") are just as important as prose — they often contain field mappings, attribute lists, and campaign matrices that are the actual technical substance of the document. Read every row.

You always respond with valid JSON only — no explanation, no markdown, no preamble."""


def _build_prompt(section_title: str, section_text: str, sec_id: str) -> str:
    return f"""Read this section of a Business Requirements Document with the eye of a Principal AEP Solution Architect.

SECTION TITLE: {section_title}

SECTION CONTENT:
{section_text}

YOUR MISSION: Extract every REAL requirement — the substance, not the packaging.

WHAT COUNTS AS A REAL REQUIREMENT (extract all of these):
- Something that must be BUILT (a model, schema, dataset, dashboard, report)
- Data that must be INGESTED (name the source: S3, Redshift, Analytics, etc.)
- A system that must be INTEGRATED (name it)
- A metric, threshold, or success criterion (e.g. "R-squared > 0.7", specific KPIs)
- A business goal that drives technical work (e.g. "measure incrementality")
- A data input, variable, channel, or factor the solution must handle
- A field, attribute, or mapping listed in a table
- A constraint (timeline, data quality, compliance, performance)
- A dependency on another team, system, or deliverable
- A use case or scenario the solution must support

WHAT TO IGNORE (do NOT create requirements for these):
- Document version numbers, revision history, author names, dates
- Table of contents entries
- Pure document-formatting details (titles, headings, page layout)
- Boilerplate about what the document itself is

CRITICAL RULES:
- If a section is pure boilerplate (version control, TOC), return an empty array [].
- If a section is rich prose or a data table, read it slowly and extract EVERY distinct requirement.
- One sentence — or one table row — can contain multiple requirements. Split them.
- Name specific technologies, metrics, and systems exactly as written.
- Capture numeric thresholds precisely.

For each real requirement return a JSON object:
- "text": the requirement stated as an actionable technical need (specific, AEP terminology)
- "verbatim_quote": the exact sentence, phrase, or table row this came from
- "type": one of "explicit", "implicit", "constraint", "assumption", "dependency", "success_metric", "data_input", "integration"
- "aep_relevance": one of "schema", "dataset", "ingestion", "modeling", "activation", "governance", "reporting", "general"
- "business_value": one sentence on why this matters to the business
- "risk_if_missed": one sentence on what breaks if this is not implemented

Return a JSON array only. No markdown, no other text.
If the section is pure boilerplate with no real requirements, return []."""


async def _extract_once(section_title: str, section_text: str, sec_id: str, semaphore: asyncio.Semaphore) -> tuple[list, str | None]:
    """Returns (observations, error). error is None on success — including a
    legitimate "this section has no real requirements" — and is set only
    when the underlying LLM call itself failed, so callers can tell those
    two cases apart instead of treating every failure as a quiet empty."""
    async with semaphore:
        try:
            data, _provider = await call_llm_json(
                _build_prompt(section_title, section_text, sec_id),
                system=SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"Section {sec_id} observation extraction failed: {e}")
            return [], str(e)
    return (data if isinstance(data, list) else []), None


async def extract_observations_from_section(section: dict, semaphore: asyncio.Semaphore) -> tuple[list, str | None]:
    section_text = section.get("content", "")
    section_title = section.get("title", "Unknown Section")
    sec_id = section.get("sec_id", "S-000")

    if len(section_text.strip()) < 5:
        return [], None

    observations, error = await _extract_once(section_title, section_text, sec_id, semaphore)

    # LLM extraction has non-trivial variance run-to-run. A substantial section
    # (real prose or a table) coming back empty is more likely a fluke than a
    # genuinely empty section, so we get one free retry before accepting it —
    # this is what keeps the "never miss a requirement" guarantee honest.
    if not observations and len(section_text.strip()) > 200:
        print(f"Section {sec_id} returned 0 observations on a non-trivial section — retrying once")
        observations, error = await _extract_once(section_title, section_text, sec_id, semaphore)

    for obs in observations:
        obs["aep_relevance"] = sanitize_layer(obs.get("aep_relevance"))
    return observations, error


async def run_pass1(section_map: dict, max_concurrency: int = _DEFAULT_CONCURRENCY, on_progress=None) -> list:
    sections = section_map.get("sections", [])
    semaphore = asyncio.Semaphore(max_concurrency)
    completed = 0

    async def worker(index: int, section: dict):
        nonlocal completed
        # A small stagger so concurrent workers don't all fire in the exact
        # same instant — several real providers rate-limit bursts of
        # simultaneous connections from one source regardless of which API
        # key each request uses, so this is cheap insurance against that.
        await asyncio.sleep(index * _STAGGER_DELAY_S)
        observations, error = await extract_observations_from_section(section, semaphore)
        completed += 1
        if on_progress:
            await on_progress(completed, len(sections), section, len(observations))
        return section, observations, error

    results = await asyncio.gather(*(worker(i, s) for i, s in enumerate(sections)))

    failures = [error for _, _, error in results if error is not None]
    if sections and failures and len(failures) == len(sections):
        raise RuntimeError(
            f"Observation extraction failed for all {len(sections)} section(s) — "
            f"the underlying LLM call never succeeded. Last error: {failures[-1]}"
        )

    results_by_sec_id = {section["sec_id"]: obs for section, obs, _error in results}

    all_observations: list = []
    for section in sections:
        observations = results_by_sec_id.get(section["sec_id"], [])
        for i, obs in enumerate(observations):
            obs["obs_id"] = f"{section['sec_id']}-O{i + 1:02d}"
            obs["section_title"] = section["title"]
            obs["sec_id"] = section["sec_id"]
        all_observations.extend(observations)

    return all_observations
