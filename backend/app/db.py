"""SQLite persistence for job history and the content-hash result cache.

Plain stdlib sqlite3 is plenty fast for a single-user local tool — no need
for an async driver or external database.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from app.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT,
                followups_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_job_id ON chat_messages(job_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_progress (
                job_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (job_id, task_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_howto (
                job_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (job_id, task_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_payload (
                job_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (job_id, task_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_execution (
                job_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                status_code INTEGER,
                ok INTEGER NOT NULL,
                response_json TEXT,
                endpoint TEXT,
                error TEXT,
                executed_at TEXT NOT NULL,
                PRIMARY KEY (job_id, task_id)
            )
        """)
        existing_exec_cols = {row["name"] for row in conn.execute("PRAGMA table_info(task_execution)")}
        if "simulated" not in existing_exec_cols:
            conn.execute("ALTER TABLE task_execution ADD COLUMN simulated INTEGER DEFAULT 0")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                color TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_job_id ON team_members(job_id)")

        # task_progress predates the assignment feature — add the column if
        # it isn't there yet rather than requiring a fresh database.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(task_progress)")}
        if "assigned_to" not in existing_cols:
            conn.execute("ALTER TABLE task_progress ADD COLUMN assigned_to TEXT")


def create_job(filename: str, content_hash: str) -> str:
    job_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, filename, content_hash, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, filename, content_hash, "queued", datetime.now(timezone.utc).isoformat()),
        )
    return job_id


def complete_job(job_id: str, result: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'done', result_json = ? WHERE id = ?",
            (json.dumps(result), job_id),
        )


def fail_job(job_id: str, error: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status = 'error', error = ? WHERE id = ?", (error, job_id))


def find_cached_result_by_hash(content_hash: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT result_json FROM jobs WHERE content_hash = ? AND status = 'done' "
            "ORDER BY created_at DESC LIMIT 1",
            (content_hash,),
        ).fetchone()
    return json.loads(row["result_json"]) if row and row["result_json"] else None


def get_job(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    job = dict(row)
    if job.get("result_json"):
        job["result"] = json.loads(job["result_json"])
    return job


def list_jobs(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, status, created_at FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_chat_message(
    job_id: str, role: str, content: str, citations: list[str] | None = None, followups: list[str] | None = None
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (job_id, role, content, citations_json, followups_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                role,
                content,
                json.dumps(citations) if citations else None,
                json.dumps(followups) if followups else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_chat_history(job_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, citations_json, followups_json, created_at FROM chat_messages "
            "WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
    messages = []
    for r in rows:
        msg = dict(r)
        citations_json = msg.pop("citations_json")
        followups_json = msg.pop("followups_json")
        msg["citations"] = json.loads(citations_json) if citations_json else []
        msg["followups"] = json.loads(followups_json) if followups_json else []
        messages.append(msg)
    return messages


def set_task_status(job_id: str, task_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_progress (job_id, task_id, status, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(job_id, task_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
            (job_id, task_id, status, datetime.now(timezone.utc).isoformat()),
        )


def get_task_progress(job_id: str) -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT task_id, status FROM task_progress WHERE job_id = ?", (job_id,)
        ).fetchall()
    return {r["task_id"]: r["status"] for r in rows}


def save_task_howto(job_id: str, task_id: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_howto (job_id, task_id, content, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(job_id, task_id) DO UPDATE SET content = excluded.content, created_at = excluded.created_at",
            (job_id, task_id, content, datetime.now(timezone.utc).isoformat()),
        )


def get_task_howto(job_id: str, task_id: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT content FROM task_howto WHERE job_id = ? AND task_id = ?", (job_id, task_id)
        ).fetchone()
    return row["content"] if row else None


def save_task_payload(job_id: str, task_id: str, content: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_payload (job_id, task_id, content, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(job_id, task_id) DO UPDATE SET content = excluded.content, created_at = excluded.created_at",
            (job_id, task_id, json.dumps(content), datetime.now(timezone.utc).isoformat()),
        )


def get_task_payload(job_id: str, task_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT content FROM task_payload WHERE job_id = ? AND task_id = ?", (job_id, task_id)
        ).fetchone()
    return json.loads(row["content"]) if row else None


def save_task_execution(
    job_id: str, task_id: str, ok: bool, status_code: int | None, response: object, endpoint: str | None,
    error: str | None = None, simulated: bool = False,
) -> dict:
    executed_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_execution (job_id, task_id, status_code, ok, response_json, endpoint, error, executed_at, simulated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(job_id, task_id) DO UPDATE SET status_code = excluded.status_code, ok = excluded.ok, "
            "response_json = excluded.response_json, endpoint = excluded.endpoint, error = excluded.error, "
            "executed_at = excluded.executed_at, simulated = excluded.simulated",
            (job_id, task_id, status_code, int(ok), json.dumps(response), endpoint, error, executed_at, int(simulated)),
        )
    return {
        "ok": ok, "status_code": status_code, "response": response, "endpoint": endpoint,
        "error": error, "executed_at": executed_at, "simulated": simulated,
    }


def get_task_execution(job_id: str, task_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM task_execution WHERE job_id = ? AND task_id = ?", (job_id, task_id)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["ok"] = bool(d["ok"])
    d["simulated"] = bool(d.get("simulated"))
    d["response"] = json.loads(d.pop("response_json")) if d.get("response_json") else None
    return d


_AVATAR_COLORS = ["#B8781F", "#0A96A8", "#8B5CF6", "#D63384", "#5B8DEF", "#16A34A"]


def add_team_member(job_id: str, name: str, role: str) -> dict:
    member_id = str(uuid.uuid4())
    color = _AVATAR_COLORS[hash(name.lower().strip()) % len(_AVATAR_COLORS)]
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO team_members (id, job_id, name, role, color, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (member_id, job_id, name.strip(), role, color, created_at),
        )
    return {"id": member_id, "job_id": job_id, "name": name.strip(), "role": role, "color": color, "created_at": created_at}


def get_team_members(job_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM team_members WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def remove_team_member(job_id: str, member_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM team_members WHERE job_id = ? AND id = ?", (job_id, member_id))
        conn.execute(
            "UPDATE task_progress SET assigned_to = NULL WHERE job_id = ? AND assigned_to = ?",
            (job_id, member_id),
        )


def assign_task(job_id: str, task_id: str, member_id: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_progress (job_id, task_id, status, assigned_to, updated_at) "
            "VALUES (?, ?, 'pending', ?, ?) "
            "ON CONFLICT(job_id, task_id) DO UPDATE SET assigned_to = excluded.assigned_to, updated_at = excluded.updated_at",
            (job_id, task_id, member_id, datetime.now(timezone.utc).isoformat()),
        )


def get_task_assignments(job_id: str) -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT task_id, assigned_to FROM task_progress WHERE job_id = ? AND assigned_to IS NOT NULL",
            (job_id,),
        ).fetchall()
    return {r["task_id"]: r["assigned_to"] for r in rows}
