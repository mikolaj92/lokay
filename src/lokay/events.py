"""Event log. Not imported by any runtime path."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

KINDS = frozenset({
    "admitted", "building", "pr_draft", "reviewing", "awaiting_human", "merged",
    "repairing", "needs_human", "parked", "dropped", "human_owned", "quarantined",
    "unquarantined", "owner_feedback", "pr_merged", "pr_closed", "run_lost",
    "outcome_recorded", "pr_published", "reviewed", "lens_scored", "disposition",
    "verdict_published", "stale_decided", "doctor", "host_action", "failure_decided",
    "backoff", "infra_paused", "labels_stripped",
})
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events("
    "id INTEGER PRIMARY KEY, ts TEXT NOT NULL, work_id TEXT, "
    "kind TEXT NOT NULL, idem TEXT NOT NULL UNIQUE, data TEXT NOT NULL)"
)


class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute(SCHEMA)
        self.db.execute("CREATE INDEX IF NOT EXISTS events_work ON events(work_id, id)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS leases("
            "resource TEXT PRIMARY KEY, holder TEXT NOT NULL, "
            "token INTEGER NOT NULL, expires_at TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seq(name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
        )
        self.db.commit()

    def append(self, kind, *, work_id, idem, data):
        if kind not in KINDS:
            raise ValueError(kind)
        try:
            cur = self.db.execute(
                "INSERT INTO events(ts, work_id, kind, idem, data) VALUES(datetime('now'), ?, ?, ?, ?)",
                (work_id, kind, idem, json.dumps(data, sort_keys=True)),
            )
        except sqlite3.IntegrityError:
            return None
        self.db.commit()
        return int(cur.lastrowid)

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def acquire(self, resource, holder, ttl_s=300):
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute(
            "SELECT token FROM leases WHERE resource=? AND expires_at > datetime('now')",
            (resource,),
        ).fetchone()
        if row is not None:
            self.db.commit()
            return None
        cur = self.db.execute(
            "INSERT INTO seq(name, value) VALUES('lease', 1) "
            "ON CONFLICT(name) DO UPDATE SET value = value + 1 RETURNING value"
        )
        token = int(cur.fetchone()[0])
        self.db.execute("DELETE FROM leases WHERE resource=?", (resource,))
        self.db.execute(
            "INSERT INTO leases(resource, holder, token, expires_at) "
            "VALUES(?, ?, ?, datetime('now', ?))",
            (resource, holder, token, f"+{int(ttl_s)} seconds"),
        )
        self.db.commit()
        return token

    def check(self, resource, token):
        row = self.db.execute(
            "SELECT 1 FROM leases WHERE resource=? AND token=? AND expires_at > datetime('now')",
            (resource, token),
        ).fetchone()
        return row is not None

    def heartbeat(self, resource, token, ttl_s=300):
        cur = self.db.execute(
            "UPDATE leases SET expires_at=datetime('now', ?) WHERE resource=? AND token=? AND expires_at > datetime('now')",
            (f"+{int(ttl_s)} seconds", resource, token),
        )
        self.db.commit()
        return cur.rowcount == 1

    def release(self, resource, token):
        self.db.execute("DELETE FROM leases WHERE resource=? AND token=?", (resource, token))
        self.db.commit()

    def held(self, prefix="repo:"):
        return self.db.execute(
            "SELECT resource, holder, token FROM leases WHERE resource LIKE ? AND expires_at > datetime('now')",
            (prefix + "%",),
        ).fetchall()


def blob_put(data: bytes) -> str:
    import hashlib
    import os
    digest = hashlib.sha256(data).hexdigest()
    root = Path(os.environ.get("HOME", ".")) / ".lokay" / "blobs" / "sha256" / digest[:2]
    root.mkdir(parents=True, exist_ok=True)
    path = root / digest[2:]
    if not path.exists():
        path.write_bytes(data)
    return "sha256:" + digest


def blob_get(ref: str) -> bytes:
    import hashlib
    import os
    digest = ref.removeprefix("sha256:")
    path = Path(os.environ.get("HOME", ".")) / ".lokay" / "blobs" / "sha256" / digest[:2] / digest[2:]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("blob hash mismatch")
    return data


TRANSITIONS = {
    "admitted": "admitted",
    "building": "building",
    "pr_published": "pr_draft",
    "reviewed": "reviewing",
    "verdict_published": "awaiting_human",
    "pr_merged": "merged",
    "pr_closed": "dropped",
    "owner_feedback": "needs_human",
    "human_owned": "human_owned",
    "run_lost": "repairing",
    "failure_decided": "parked",
    "quarantined": "quarantined",
    "unquarantined": "admitted",
}


def project_work_items(events):
    items = {}
    for event in events:
        state = TRANSITIONS.get(event["kind"])
        if state is None or not event.get("work_id"):
            continue
        items[event["work_id"]] = state
    return items
