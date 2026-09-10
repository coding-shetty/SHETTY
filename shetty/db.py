from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text',
    tool_calls TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, due_at TEXT, completed INTEGER NOT NULL DEFAULT 0,
    notified_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS roots (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, path TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
    tool TEXT NOT NULL, arguments TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
    result TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, category TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


class Store:
    """Small local store. Connections are short-lived and safe across request threads."""

    def __init__(self, data_dir: Path):
        if data_dir.resolve() in {Path("/"), Path.home().resolve()} or data_dir.is_symlink():
            raise ValueError("Use a dedicated, non-symlink directory for SHETTY's private data.")
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Only chmod our dedicated directory, never a user-supplied parent.
        data_dir.chmod(0o700)
        self.path = data_dir / "shetty.sqlite3"
        if self.path.is_symlink():
            raise ValueError("The database must not be a symbolic link.")
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connect() as conn:
            if conn.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError("This database belongs to a newer version of SHETTY. Do not downgrade it.")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    def recover_interrupted_actions(self) -> None:
        # Only run after acquiring the exclusive server lock, not on every Store
        # construction (another process may simply be reading the database).
        with self.connect() as conn:
            # Never retry an action that might already have happened before a crash.
            conn.execute(
                "UPDATE proposals SET status='failed', result=? WHERE status='running'",
                (json.dumps({"error": "Interrupted by a restart. The action may have completed; check before retrying."}),),
            )

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def one(self, sql: str, args: tuple = ()) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(sql, args).fetchone()
            return dict(row) if row else None

    def all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def setting(self, key: str, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))

    def event(self, category: str, title: str, detail: str = "") -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", (new_id(), category, title, detail, now_iso()))
            # Bound the audit journal. Chat and memories are kept until the user deletes them.
            conn.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY created_at DESC LIMIT 1000)")

    def create_conversation(self) -> dict:
        record = {"id": new_id(), "title": "New conversation", "created_at": now_iso(), "updated_at": now_iso()}
        with self.connect() as conn:
            conn.execute("INSERT INTO conversations VALUES (:id, :title, :created_at, :updated_at)", record)
        return record

    def conversation(self, conversation_id: str) -> dict | None:
        return self.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))

    def conversations(self) -> list[dict]:
        return self.all("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 100")

    def add_message(self, conversation_id: str, role: str, content: str, *, kind="text", tool_calls=None) -> dict:
        record = {
            "id": new_id(), "conversation_id": conversation_id, "role": role, "content": content,
            "kind": kind, "tool_calls": json.dumps(tool_calls or []), "created_at": now_iso(),
        }
        with self.connect() as conn:
            conn.execute("""INSERT INTO messages (id, conversation_id, role, content, kind, tool_calls, created_at)
                VALUES (:id, :conversation_id, :role, :content, :kind, :tool_calls, :created_at)""", record)
            conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now_iso(), conversation_id))
            if role == "user":
                conn.execute("UPDATE conversations SET title=? WHERE id=? AND title='New conversation'", (content[:55], conversation_id))
        record["tool_calls"] = tool_calls or []
        return record

    def messages(self, conversation_id: str) -> list[dict]:
        rows = self.all("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at, rowid", (conversation_id,))
        for row in rows:
            row["tool_calls"] = json.loads(row["tool_calls"])
        return rows

    def delete_conversation(self, conversation_id: str) -> bool:
        with self.connect() as conn:
            return bool(conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,)).rowcount)

    def memories(self, query: str = "") -> list[dict]:
        if not query:
            return self.all("SELECT * FROM memories ORDER BY updated_at DESC")
        # Escape LIKE metacharacters so searches are literal, not SQL wildcards.
        value = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self.all("SELECT * FROM memories WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' ORDER BY updated_at DESC", (value, value))

    def save_memory(self, title: str, content: str, kind: str, memory_id: str | None = None) -> dict:
        record = {"id": memory_id or new_id(), "title": title, "content": content, "kind": kind, "updated_at": now_iso()}
        with self.connect() as conn:
            if memory_id:
                if not conn.execute("UPDATE memories SET title=:title, content=:content, kind=:kind, updated_at=:updated_at WHERE id=:id", record).rowcount:
                    raise KeyError("Memory not found.")
            else:
                conn.execute("INSERT INTO memories VALUES (:id, :title, :content, :kind, :updated_at, :updated_at)", record)
        return self.one("SELECT * FROM memories WHERE id=?", (record["id"],))

    def memory_context(self, query: str, budget: int = 1500) -> str:
        terms = set(re.findall(r"\w{3,}", query.casefold()))
        scored = []
        for row in self.memories():
            text = f"{row['title']}: {row['content']}"
            score = sum(term in text.casefold() for term in terms) + (3 if row["kind"] == "preference" else 0)
            if score:
                scored.append((score, text))
        scored.sort(key=lambda item: item[0], reverse=True)
        return "\n\n".join(text for _, text in scored[:8])[:budget]

    def delete_record(self, table: str, record_id: str) -> bool:
        if table not in {"memories", "tasks", "roots"}:
            raise ValueError("Unsupported table.")
        with self.connect() as conn:
            return bool(conn.execute(f"DELETE FROM {table} WHERE id=?", (record_id,)).rowcount)

    def add_task(self, title: str, due_at: str | None = None) -> dict:
        if due_at is not None:
            parsed = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Task times must include a timezone.")
            due_at = parsed.astimezone(timezone.utc).isoformat()
        record = {"id": new_id(), "title": title, "due_at": due_at, "created_at": now_iso()}
        with self.connect() as conn:
            conn.execute("INSERT INTO tasks (id, title, due_at, created_at) VALUES (:id, :title, :due_at, :created_at)", record)
        return self.one("SELECT * FROM tasks WHERE id=?", (record["id"],))

    def tasks(self) -> list[dict]:
        return self.all("SELECT * FROM tasks ORDER BY completed, due_at IS NULL, due_at, created_at DESC")

    def complete_task(self, task_id: str, completed: bool) -> bool:
        with self.connect() as conn:
            return bool(conn.execute("UPDATE tasks SET completed=? WHERE id=?", (int(completed), task_id)).rowcount)

    def claim_due_tasks(self, now: str | None = None) -> list[dict]:
        """Persist notification claims and in-app events in one transaction, once only."""
        current = now or now_iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT * FROM tasks WHERE completed=0 AND notified_at IS NULL AND due_at IS NOT NULL AND due_at<=?", (current,)).fetchall()
            for row in rows:
                conn.execute("UPDATE tasks SET notified_at=? WHERE id=?", (current, row["id"]))
                conn.execute("INSERT INTO events VALUES (?, 'reminder', ?, ?, ?)", (new_id(), row["title"], "A scheduled reminder is due.", current))
            return [dict(row) for row in rows]

    def roots(self) -> list[dict]:
        return self.all("SELECT * FROM roots ORDER BY label")

    def add_root(self, label: str, path: str) -> dict:
        record = {"id": new_id(), "label": label, "path": path, "created_at": now_iso()}
        with self.connect() as conn:
            conn.execute("INSERT INTO roots VALUES (:id, :label, :path, :created_at)", record)
        return record

    def add_proposal(self, tool: str, arguments: dict, conversation_id=None, message_id=None) -> dict:
        created = datetime.now(timezone.utc)
        record = {
            "id": new_id(), "tool": tool, "arguments": json.dumps(arguments),
            "conversation_id": conversation_id, "message_id": message_id,
            "created_at": created.isoformat(), "expires_at": (created + timedelta(minutes=10)).isoformat(),
        }
        with self.connect() as conn:
            conn.execute("""INSERT INTO proposals (id, tool, arguments, conversation_id, message_id, created_at, expires_at)
                VALUES (:id, :tool, :arguments, :conversation_id, :message_id, :created_at, :expires_at)""", record)
        return self.proposal(record["id"])

    @staticmethod
    def decode_proposal(row: dict | None) -> dict | None:
        if row:
            row["arguments"] = json.loads(row["arguments"])
            row["result"] = json.loads(row["result"]) if row["result"] else None
        return row

    def expire_proposals(self) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE proposals SET status='expired' WHERE status='pending' AND expires_at<?", (now_iso(),))

    def proposal(self, proposal_id: str) -> dict | None:
        self.expire_proposals()
        return self.decode_proposal(self.one("SELECT * FROM proposals WHERE id=?", (proposal_id,)))

    def proposals(self, conversation_id: str | None = None) -> list[dict]:
        self.expire_proposals()
        if conversation_id:
            rows = self.all("SELECT * FROM proposals WHERE conversation_id=? ORDER BY created_at", (conversation_id,))
        else:
            rows = self.all("SELECT * FROM proposals ORDER BY created_at DESC LIMIT 100")
        return [self.decode_proposal(row) for row in rows]

    def claim_proposal(self, proposal_id: str, approve: bool) -> dict:
        self.expire_proposals()
        with self.connect() as conn:
            cursor = conn.execute("UPDATE proposals SET status=? WHERE id=? AND status='pending' AND expires_at>?", ("running" if approve else "denied", proposal_id, now_iso()))
            if cursor.rowcount != 1:
                raise ValueError("This request was already handled or has expired.")
        return self.proposal(proposal_id)

    def finish_proposal(self, proposal_id: str, status: str, result: dict) -> dict:
        with self.connect() as conn:
            conn.execute("UPDATE proposals SET status=?, result=? WHERE id=? AND status='running'", (status, json.dumps(result), proposal_id))
        return self.proposal(proposal_id)
