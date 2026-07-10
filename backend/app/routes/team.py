"""Team roster and task assignment.

Identity here is deliberately lightweight — name + role, no login — because
a real login system is a different project. What matters for a team working
one BRD together is: who's on it, what they're responsible for, and a
monitor of who's doing what. Auto-assignment is a starting suggestion (match
role to AEP layer), never a lock — every assignment can be overridden.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db

router = APIRouter()

ROLE_TO_LAYER = {
    "schema": "schema",
    "dataset": "dataset",
    "ingestion": "ingestion",
    "activation": "activation",
}

VALID_ROLES = {"schema", "dataset", "ingestion", "activation", "pm", "reviewer"}

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


class JoinRequest(BaseModel):
    name: str
    role: str


@router.get("/api/jobs/{job_id}/team")
async def get_team(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    members = db.get_team_members(job_id)
    assignments = db.get_task_assignments(job_id)
    counts = {m["id"]: {"assigned": 0, "done": 0} for m in members}
    if job.get("result"):
        progress = db.get_task_progress(job_id)
        for task in job["result"]["tasks"]:
            member_id = assignments.get(task["task_id"])
            if member_id and member_id in counts:
                counts[member_id]["assigned"] += 1
                if progress.get(task["task_id"]) == "done":
                    counts[member_id]["done"] += 1
    return [{**m, **counts.get(m["id"], {"assigned": 0, "done": 0})} for m in members]


@router.post("/api/jobs/{job_id}/team")
async def join_team(job_id: str, body: JoinRequest):
    if not body.name.strip():
        raise HTTPException(400, "Name is required")
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(VALID_ROLES)}")
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    member = db.add_team_member(job_id, body.name, body.role)

    # Auto-suggest: whenever the roster for a layer changes, rebalance every
    # not-yet-done task in that layer round-robin (by priority, then task id)
    # across everyone who shares it — rather than the first person to join a
    # role permanently keeping everything just because they claimed it first.
    # Completed tasks are never touched. This is a starting suggestion, not a
    # lock — every assignment can still be overridden by hand afterward.
    target_layer = ROLE_TO_LAYER.get(body.role)
    auto_assigned = 0
    if target_layer:
        peers = [m["id"] for m in db.get_team_members(job_id) if ROLE_TO_LAYER.get(m["role"]) == target_layer]
        progress = db.get_task_progress(job_id)
        pending_tasks = [
            t for t in job["result"]["tasks"]
            if t["aep_layer"] == target_layer and progress.get(t["task_id"], "pending") != "done"
        ]
        pending_tasks.sort(key=lambda t: (PRIORITY_RANK.get(t["priority"], 2), t["task_id"]))

        for i, task in enumerate(pending_tasks):
            target_member = peers[i % len(peers)]
            db.assign_task(job_id, task["task_id"], target_member)
            if target_member == member["id"]:
                auto_assigned += 1

    return {**member, "auto_assigned": auto_assigned}


@router.delete("/api/jobs/{job_id}/team/{member_id}")
async def leave_team(job_id: str, member_id: str):
    db.remove_team_member(job_id, member_id)
    return {"ok": True}


class AssignRequest(BaseModel):
    member_id: str | None = None


@router.post("/api/jobs/{job_id}/wizard/tasks/{task_id}/assign")
async def assign_task(job_id: str, task_id: str, body: AssignRequest):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")
    if body.member_id is not None:
        member_ids = {m["id"] for m in db.get_team_members(job_id)}
        if body.member_id not in member_ids:
            raise HTTPException(404, "Team member not found")
    db.assign_task(job_id, task_id, body.member_id)
    return {"ok": True}
