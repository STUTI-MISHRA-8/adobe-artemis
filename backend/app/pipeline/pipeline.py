"""Orchestrates the full parse -> extract -> structure -> plan -> trace pipeline.

Exposes an async generator that yields live progress events as each pass
runs, so the API can stream them straight to the browser over SSE — this is
what makes the UI feel alive instead of showing a blank spinner for the
duration of the whole analysis.
"""

import asyncio

from app.ingestion.sectionizer import build_section_map
from app.models import AnalysisResult, CoverageAudit
from app.pipeline.observations import run_pass1
from app.pipeline.requirements import run_coverage_audit, run_pass2
from app.pipeline.tasks import run_pass3
from app.pipeline.traceability import build_traceability


async def run_pipeline(file_path: str, filename: str, job_id: str):
    """Async generator yielding {"stage", "message", "percent"} progress dicts,
    ending with either {"stage": "done", ..., "result": {...}} or {"stage": "error", ...}.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(stage: str, message: str, percent: int):
        await queue.put({"stage": stage, "message": message, "percent": percent})

    async def worker():
        try:
            await emit("parsing", "Parsing document structure...", 3)
            section_map = await asyncio.to_thread(build_section_map, file_path)
            if "error" in section_map:
                raise ValueError(section_map["error"])

            await emit(
                "parsing",
                f"Found {section_map['section_count']} sections "
                f"({section_map['table_count']} tables) — {section_map['total_tokens']} tokens",
                10,
            )

            async def obs_progress(completed, total, section, obs_count):
                pct = 10 + int(40 * completed / total)
                title = section["title"][:45]
                await emit("extracting", f"Section {completed}/{total} — \"{title}\" — {obs_count} found", pct)

            observations = await run_pass1(section_map, on_progress=obs_progress)
            await emit("extracting", f"{len(observations)} observations extracted", 50)

            if not observations:
                raise ValueError("No requirement observations could be extracted from this document")

            async def req_progress(completed, total, count):
                pct = 50 + int(25 * completed / total)
                await emit("structuring", f"Batch {completed}/{total} structured — {count} requirement(s)", pct)

            requirements = await run_pass2(observations, on_progress=req_progress)
            if not requirements:
                raise ValueError("No requirements could be structured from this document's observations")
            coverage = run_coverage_audit(observations, requirements)
            await emit(
                "structuring",
                f"{len(requirements)} requirements formalized — {coverage['coverage_percent']}% coverage",
                75,
            )

            async def task_progress(completed, total, count):
                pct = 75 + int(20 * completed / total)
                await emit("planning", f"Batch {completed}/{total} planned — {count} task(s)", pct)

            execution_plan = await run_pass3(requirements, on_progress=task_progress)
            all_tasks = (
                execution_plan["phase_1_schema"]
                + execution_plan["phase_2_dataset"]
                + execution_plan["phase_3_ingestion"]
                + execution_plan["phase_4_activation"]
            )

            await emit("planning", "Building traceability graph...", 97)
            trace = build_traceability(observations, requirements, all_tasks)

            result = AnalysisResult(
                job_id=job_id,
                filename=filename,
                section_count=section_map["section_count"],
                observation_count=len(observations),
                requirement_count=len(requirements),
                task_count=len(all_tasks),
                coverage=CoverageAudit(**coverage),
                requirements=requirements,
                tasks=all_tasks,
                trace=trace,
                sections=[{"sec_id": s["sec_id"], "title": s["title"], "content": s["content"]} for s in section_map["sections"]],
            ).model_dump()

            await queue.put({"stage": "done", "message": "Analysis complete", "percent": 100, "result": result})
        except Exception as e:
            await queue.put({"stage": "error", "message": str(e), "percent": 100})
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await task
