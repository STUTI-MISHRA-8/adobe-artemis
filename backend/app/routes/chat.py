"""Ask-the-document Q&A — streaming, multi-turn, and grounded in the right data source.

Two retrieval modes feed the LLM, chosen by intent:
  - Coverage/completeness questions ("what's not covered", "list every gap") are
    grounded in the already-computed structured analysis (requirements +
    orphaned observations) instead of raw prose — the pipeline already did
    this work, so re-deriving it from text is both slower and less accurate.
  - Broad "list everything" questions get the full document instead of a
    top-k section slice, since these BRDs are small enough (10-40K tokens)
    to fit entirely.
  - Everything else uses keyword-overlap retrieval over sections, blended
    with the previous user turn so follow-ups ("ok cover them") retrieve
    against what was actually being discussed, not just the follow-up's own
    (often contentless) words.

No vector DB, no extra infrastructure — the retrieval trick is choosing the
right pre-computed context, not fancier search.
"""

import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import db
from app.llm.router import stream_llm

router = APIRouter()

SYSTEM_PROMPT = """You are an assistant answering questions about a specific Business Requirements Document and its AEP implementation analysis.
Answer ONLY using the provided context. If the answer isn't in it, say so clearly — never guess or invent details.
Always cite which section(s) or requirement(s) you used, like (S-004) or (R-012).
If earlier conversation turns are provided, use them to resolve references like "it", "them", or "that".

After your answer, on a new line, always add exactly this block with 2-3 short natural follow-up questions a user would plausibly ask next, grounded in what you just discussed:
<<<FOLLOWUPS>>>
- follow up question 1
- follow up question 2"""

STOPWORDS = {"the", "a", "an", "is", "are", "of", "to", "in", "for", "and", "or", "what", "how", "does", "do", "on", "with", "this", "that", "ok", "okay"}
DELIMITER = "<<<FOLLOWUPS>>>"

COVERAGE_KEYWORDS = {"not covered", "uncovered", "missing", "gap", "gaps", "orphan", "orphaned", "coverage", "complete", "completeness", "left out", "unaddressed"}
BROAD_KEYWORDS = {"every", "all fields", "all sections", "all requirements", "entire document", "whole document", "list every", "everything"}


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 2}


def _top_sections(sections: list[dict], query: str, k: int = 5) -> list[dict]:
    q_tokens = _tokenize(query)
    scored = []
    for s in sections:
        s_tokens = _tokenize(s["title"] + " " + s["content"])
        score = len(q_tokens & s_tokens)
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for score, s in scored[:k] if score > 0]
    return top or sections[:k]


def _is_coverage_question(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in COVERAGE_KEYWORDS)


def _is_broad_question(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in BROAD_KEYWORDS)


def _build_coverage_context(result: dict) -> tuple[str, list[str]]:
    coverage = result["coverage"]
    requirements = result["requirements"]
    orphan_ids = set(coverage["orphaned_observations"])

    obs_by_id = {obs["obs_id"]: obs for section in result.get("trace", []) for obs in section.get("observations", [])}
    orphan_lines = [f"- {oid}: {obs_by_id[oid]['text']}" for oid in orphan_ids if oid in obs_by_id]

    # True orphans are near-impossible here — every observation that doesn't fit
    # a real requirement is auto-captured into an "unclassified" catch-all
    # requirement instead of being dropped. THAT flag is the honest signal for
    # "not cleanly covered", not the (usually empty) raw orphan list.
    unclassified = [r for r in requirements if "unclassified" in r.get("flags", [])]
    unclassified_lines = [f"- {r['req_id']}: covers {', '.join(r['source_obs'])} — {r['description']}" for r in unclassified]

    req_lines = [f"- {r['req_id']} [{r['aep_layer']}/{r['priority']}]: {r['description']}" for r in requirements]

    context = f"""ANALYSIS COVERAGE SUMMARY (computed directly from the document, authoritative):
Total observations: {coverage['total_observations']}
Mapped to requirements: {coverage['mapped_observations']}
Coverage: {coverage['coverage_percent']}%

Raw orphaned observations ({len(orphan_lines)} — not mapped to ANY requirement, including catch-alls):
{chr(10).join(orphan_lines) if orphan_lines else "(none)"}

Requirements flagged "unclassified" ({len(unclassified_lines)} — these are catch-all requirements auto-created for observations that didn't fit any real requirement; this is the honest answer to "what's not properly covered"):
{chr(10).join(unclassified_lines) if unclassified_lines else "(none — every observation was cleanly covered by a real requirement)"}

ALL REQUIREMENTS ({len(req_lines)}):
{chr(10).join(req_lines)}"""
    return context, ["coverage-summary"] + [r["req_id"] for r in requirements[:20]]


def _build_broad_context(sections: list[dict]) -> tuple[str, list[str]]:
    context = "\n\n".join(f"[{s['sec_id']}] {s['title']}\n{s['content'][:4000]}" for s in sections)
    return context, [s["sec_id"] for s in sections]


def _build_retrieval_context(sections: list[dict], question: str, history: list[dict]) -> tuple[str, list[str]]:
    retrieval_query = question
    if history:
        last_user_turn = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
        retrieval_query = f"{last_user_turn} {question}"
    relevant = _top_sections(sections, retrieval_query)
    context = "\n\n".join(f"[{s['sec_id']}] {s['title']}\n{s['content'][:2500]}" for s in relevant)
    return context, [s["sec_id"] for s in relevant]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatTurn] = []


@router.get("/api/jobs/{job_id}/chat")
async def get_chat_history(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return db.get_chat_history(job_id)


@router.post("/api/jobs/{job_id}/chat")
async def chat_with_document(job_id: str, body: ChatRequest):
    job = db.get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Completed job not found")

    result = job["result"]
    sections = result.get("sections", [])
    if not sections:
        raise HTTPException(400, "No document sections available for this job")

    history = [h.model_dump() for h in body.history]

    if _is_coverage_question(body.question):
        context, citations = _build_coverage_context(result)
    elif _is_broad_question(body.question):
        context, citations = _build_broad_context(sections)
    else:
        context, citations = _build_retrieval_context(sections, body.question, history)

    history_text = ""
    if history:
        turns = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-8:])
        history_text = f"\nCONVERSATION SO FAR:\n{turns}\n"

    prompt = f"""CONTEXT:
{context}
{history_text}
NEW QUESTION: {body.question}

Answer concisely and cite sources used."""

    db.save_chat_message(job_id, "user", body.question)

    async def event_stream():
        full_text = ""
        pending = ""
        delimiter_found = False
        provider_used = "fluffy"

        async for chunk, provider in stream_llm(prompt, system=SYSTEM_PROMPT):
            provider_used = provider
            full_text += chunk
            if delimiter_found:
                continue
            pending += chunk
            if DELIMITER in pending:
                before, _, _after = pending.partition(DELIMITER)
                if before:
                    yield _sse("chunk", {"text": before})
                delimiter_found = True
                pending = ""
                continue
            safe_len = max(0, len(pending) - (len(DELIMITER) - 1))
            if safe_len > 0:
                yield _sse("chunk", {"text": pending[:safe_len]})
                pending = pending[safe_len:]

        if not delimiter_found and pending:
            yield _sse("chunk", {"text": pending})

        if DELIMITER in full_text:
            answer_text, _, followup_block = full_text.partition(DELIMITER)
        else:
            answer_text, followup_block = full_text, ""
        answer_text = answer_text.strip()
        followups = [
            line.strip("-• ").strip()
            for line in followup_block.splitlines()
            if line.strip().startswith(("-", "•"))
        ][:3]

        db.save_chat_message(job_id, "assistant", answer_text, citations=citations, followups=followups)
        yield _sse("done", {"answer": answer_text, "citations": citations, "followups": followups, "provider": provider_used})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
