# Adobe Artemis

Turn an AEP solution/requirements document into an actionable implementation plan.

Upload a PDF or DOCX requirements doc and Artemis runs it through an LLM
pipeline that extracts observations, structures them into discrete
implementation requirements, and organizes them by Adobe Experience Platform
(AEP) phase — schema → dataset → ingestion → activation. Each requirement
becomes a step-by-step wizard task with click-by-click AEP UI instructions
and ready-to-use REST API payloads (Schema Registry, Catalog Service, Flow
Service, Segmentation Service, Destinations/Data Governance). A job also
gets a chat interface for follow-up questions and an export option.

Built for AEP solution architects and implementation engineers who need to
go from "here's the SOW" to concrete build steps.

## Stack

**Backend** — FastAPI (Python), SQLite, PyMuPDF/python-docx for document
ingestion, SSE for streaming job progress. LLM calls route across three
providers with automatic fallback: Groq (`llama-3.3-70b-versatile`, with
multi-key rotation for quota), Gemini (`gemini-flash-latest`), and an
internal Adobe LLM gateway. A dedicated AEP client talks to the real AEP
APIs for status checks.

**Frontend** — Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS
v4, shadcn/Base UI, Framer Motion.

**Deployment** — Render.com (`render.yaml`, Docker).

## Running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # or venv/bin/activate on macOS/Linux
pip install -r requirements.txt
# create .env with the variables listed below
uvicorn app.main:app --host 0.0.0.0 --port 8011
```

### Frontend

```bash
cd frontend
npm install
# create .env.local with NEXT_PUBLIC_API_BASE pointing at the backend
npm run dev
```

Open the URL Next.js prints (defaults to `http://localhost:3000`).

### Environment variables

Backend (`backend/.env`):

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` / `GROQ_API_KEY_1..10` / `GROQ_API_KEYS` | Groq keys (any combination), rotated for quota |
| `GEMINI_API_KEY` | Gemini fallback |
| `FLUFFYJAWS_API_HOST`, `FLUFFYJAWS_MODEL` | Internal Adobe LLM gateway |
| `AEP_CLIENT_ID`, `AEP_CLIENT_SECRET`, `AEP_ORG_ID`, `AEP_SANDBOX_NAME`, `AEP_SCOPES` | AEP OAuth credentials |
| `CORS_ORIGINS` | Comma-separated allowed origins (defaults to `http://localhost:3000`) |

Frontend (`frontend/.env.local`):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE` | Backend base URL, e.g. `http://localhost:8011` |

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/analyze` | Upload a document and kick off a job |
| `GET /api/jobs` | List jobs |
| `GET /api/jobs/{job_id}/stream` | SSE stream of pipeline progress |
| `GET /api/jobs/{job_id}/wizard` | Step-by-step implementation wizard |
| `GET /api/jobs/{job_id}/chat` | Chat about the job |
| `GET /api/jobs/{job_id}/team` | Team view |
| `GET /api/jobs/{job_id}/export` | Export the plan |
| `GET /api/config/aep-status` | Whether AEP credentials are configured |
| `GET /api/config/llm-status` | LLM key counts (no key material) |
