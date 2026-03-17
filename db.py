"""
SQLite database helpers for the bot.

This creates a local database file `bot.db` next to this file and stores reports in
the `reports` table.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Database file: ./bot.db (in the same folder as db.py)
DB_PATH = Path(__file__).with_name("bot.db")


@contextmanager
def _connect():
    # `check_same_thread=False` is a safe default for Discord bots where commands may
    # run in different tasks/threads depending on the runtime. SQLite will still
    # serialize writes internally.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def setup() -> None:
    """Create the `reports` table if it doesn't exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )


def add_report(user_id: str, reason: str) -> int:
    """Insert a report and return its new ID."""
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO reports (user_id, reason, created_at) VALUES (?, ?, ?)",
            (user_id, reason, created_at),
        )
        return int(cur.lastrowid)


def get_reports() -> list[dict[str, Any]]:
    """Return all reports as a list of dicts (newest first)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, user_id, reason, created_at FROM reports ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_report(report_id: int) -> bool:
    """Delete by ID. Returns True if something was deleted."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cur.rowcount > 0

