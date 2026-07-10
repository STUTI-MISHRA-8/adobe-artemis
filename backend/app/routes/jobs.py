from fastapi import APIRouter, HTTPException

from app import db

router = APIRouter()


@router.get("/api/jobs")
async def list_jobs():
    return db.list_jobs()


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
