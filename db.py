"""
SQLite database helpers for the bot.

Creates a local database file `bot.db` and stores reports in `reports` table.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ------------------ DB PATH ------------------
DB_PATH = Path(__file__).with_name("bot.db")


# ------------------ CONNECTION ------------------
@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ------------------ SETUP ------------------
def setup() -> None:
    """Create table if not exists."""
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)


# ------------------ ADD REPORT ------------------
def add_report(user_id: str, reason: str) -> int:
    """Insert a report and return its ID."""
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO reports (user_id, reason, created_at) VALUES (?, ?, ?)",
            (user_id, reason, now)
        )
        return cur.lastrowid


# ------------------ GET REPORTS ------------------
def get_reports() -> list[dict[str, Any]]:
    """Fetch all reports (newest first)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, user_id, reason, created_at FROM reports ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------ DELETE REPORT ------------------
def delete_report(report_id: int) -> bool:
    """Delete report by ID."""
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM reports WHERE id = ?",
            (report_id,)
        )
        return cur.rowcount > 0
