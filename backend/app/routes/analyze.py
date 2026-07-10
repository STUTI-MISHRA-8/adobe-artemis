import pathlib

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import db
from app.cache import hash_bytes
from app.config import DATA_DIR

router = APIRouter()

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/api/analyze")
async def analyze_document(file: UploadFile = File(...)):
    suffix = pathlib.Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Please upload a PDF or DOCX.")

    content = await file.read()
    content_hash = hash_bytes(content)

    cached_result = db.find_cached_result_by_hash(content_hash)
    if cached_result:
        job_id = db.create_job(file.filename, content_hash)
        db.complete_job(job_id, {**cached_result, "job_id": job_id, "filename": file.filename})
        return {"job_id": job_id, "cached": True}

    job_id = db.create_job(file.filename, content_hash)
    dest_path = UPLOAD_DIR / f"{job_id}{suffix}"
    dest_path.write_bytes(content)

    return {"job_id": job_id, "cached": False}
