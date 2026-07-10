import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app import db
from app.pipeline.pipeline import run_pipeline
from app.routes.analyze import UPLOAD_DIR

router = APIRouter()


@router.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if job["status"] == "done":
        async def cached_event_generator():
            yield {"event": "progress", "data": json.dumps({"stage": "done", "message": "Loaded from cache", "percent": 100})}
            yield {"event": "result", "data": json.dumps(job["result"])}

        return EventSourceResponse(cached_event_generator())

    matches = list(UPLOAD_DIR.glob(f"{job_id}.*"))
    if not matches:
        raise HTTPException(404, "Uploaded file not found for this job")
    file_path = str(matches[0])

    async def event_generator():
        async for event in run_pipeline(file_path, job["filename"], job_id):
            if event["stage"] == "done":
                db.complete_job(job_id, event["result"])
                yield {"event": "progress", "data": json.dumps({k: v for k, v in event.items() if k != "result"})}
                yield {"event": "result", "data": json.dumps(event["result"])}
                matches[0].unlink(missing_ok=True)
            elif event["stage"] == "error":
                db.fail_job(job_id, event["message"])
                yield {"event": "error", "data": json.dumps(event)}
            else:
                yield {"event": "progress", "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
