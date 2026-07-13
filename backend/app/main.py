from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.routes import analyze, chat, export, jobs, stream, team, wizard


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Adobe Artemis", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(stream.router)
app.include_router(jobs.router)
app.include_router(export.router)
app.include_router(chat.router)
app.include_router(wizard.router)
app.include_router(team.router)


@app.get("/")
def health():
    return {"message": "Adobe Artemis is alive"}


@app.get("/api/config/aep-status")
def aep_status():
    return {"configured": settings.aep_configured, "sandbox": settings.aep_sandbox_name or None}


@app.get("/api/config/llm-status")
def llm_status():
    """Counts only — never returns any key material, even partial. Exists purely
    to verify the running process actually picked up the configured keys, since
    env var changes and deploys can otherwise be hard to distinguish from the
    outside."""
    return {
        "groq_key_count": len(settings.groq_api_key_list),
        "gemini_configured": bool(settings.gemini_api_key),
    }
