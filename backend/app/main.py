import os
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
    """Counts and lengths only — never returns any key material, even partial.
    Exists purely to verify the running process actually picked up the
    configured keys, since env var changes and deploys can otherwise be hard
    to distinguish from the outside.

    raw_env_* reads os.environ directly, bypassing pydantic-settings entirely,
    to tell apart "Render never passed this env var to the container" from
    "it's passed through fine but something in our own parsing is wrong"."""
    raw_keys = os.environ.get("GROQ_API_KEYS")
    raw_key = os.environ.get("GROQ_API_KEY")
    return {
        "groq_key_count": len(settings.groq_api_key_list),
        "gemini_configured": bool(settings.gemini_api_key),
        "raw_env_GROQ_API_KEYS_present": raw_keys is not None,
        "raw_env_GROQ_API_KEYS_length": len(raw_keys) if raw_keys is not None else None,
        "raw_env_GROQ_API_KEY_present": raw_key is not None,
        "raw_env_GROQ_API_KEY_length": len(raw_key) if raw_key is not None else None,
    }
