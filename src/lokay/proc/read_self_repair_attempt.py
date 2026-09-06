"""Read the latest repair attempt boundary from the existing Fala journal."""

import sqlite3
from pathlib import Path


def read_started_at() -> str:
    db = Path.home() / ".lokay/fala/self-repair/state.sqlite"
    if not db.is_file():
        return ""
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT MAX(created_at) FROM runs WHERE correlation_path_id = ?",
                ("self_repair",),
            ).fetchone()
        return str(row[0] or "") if row else ""
    except sqlite3.Error:
        return ""
