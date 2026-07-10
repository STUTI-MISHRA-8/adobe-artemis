import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app import db

router = APIRouter()


def _requirements_csv(result: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["req_id", "aep_layer", "priority", "description", "source_section", "flags", "source_obs"])
    for r in result["requirements"]:
        writer.writerow([
            r["req_id"], r["aep_layer"], r["priority"], r["description"],
            r["source_section"], "|".join(r.get("flags", [])), "|".join(r.get("source_obs", [])),
        ])
    return buf.getvalue()


def _tasks_csv(result: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["task_id", "req_id", "phase", "aep_layer", "priority", "title", "description", "acceptance_criteria"])
    for t in result["tasks"]:
        writer.writerow([
            t["task_id"], t["req_id"], t["phase"], t["aep_layer"], t["priority"],
            t["title"], t["description"], t.get("acceptance_criteria", ""),
        ])
    return buf.getvalue()


def _traceability_markdown(result: dict) -> str:
    lines = [f"# Traceability Report — {result['filename']}", ""]
    lines.append(f"Coverage: {result['coverage']['coverage_percent']}% "
                 f"({result['coverage']['mapped_observations']}/{result['coverage']['total_observations']} observations mapped)")
    lines.append("")
    for node in result["trace"]:
        lines.append(f"## {node['req_id']} — {node['description']}")
        lines.append(f"*Layer: {node['aep_layer']} | Source: {node['source_section']}*")
        lines.append("")
        lines.append("**Source observations:**")
        for obs in node["observations"]:
            lines.append(f"- `{obs['obs_id']}` {obs['text']}")
        lines.append("")
        lines.append("**Tasks:**")
        for task in node["tasks"]:
            lines.append(f"- `{task['task_id']}` (Phase {task['phase']}) {task['title']}")
        lines.append("")
    return "\n".join(lines)


@router.get("/api/jobs/{job_id}/export")
async def export_job(job_id: str, format: str = Query("json", pattern="^(json|requirements_csv|tasks_csv|markdown)$")):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")
    result = job["result"]

    if format == "json":
        content, media_type, filename = json.dumps(result, indent=2), "application/json", f"{job_id}.json"
    elif format == "requirements_csv":
        content, media_type, filename = _requirements_csv(result), "text/csv", f"{job_id}_requirements.csv"
    elif format == "tasks_csv":
        content, media_type, filename = _tasks_csv(result), "text/csv", f"{job_id}_tasks.csv"
    else:
        content, media_type, filename = _traceability_markdown(result), "text/markdown", f"{job_id}_traceability.md"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
