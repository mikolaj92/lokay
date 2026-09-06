"""Validation history belongs to one SHA and its latest completed attempt."""

import json
import sqlite3

from lokay.proc.read_self_repair_validation_outcome import read_for_head


def journal(tmp_path, entries):
    folder = tmp_path / "self_repair_validate"
    folder.mkdir()
    with sqlite3.connect(folder / "state.sqlite") as conn:
        conn.execute("CREATE TABLE processes (id TEXT, status TEXT, input_json TEXT, output_json TEXT, error_json TEXT, started_at TEXT)")
        for stamp, head, result in entries:
            conn.execute("INSERT INTO processes VALUES (?, ?, ?, ?, ?, ?)", (
                "self_repair_validate:run_self_repair_tests", "completed",
                json.dumps({"head": head}), json.dumps(result), "{}", stamp,
            ))
    return {"head": "a" * 40, "journal_home": str(tmp_path)}


def test_unknown_sha_timeout_cannot_poison_candidate(tmp_path):
    candidate = journal(tmp_path, [("2026-09-06T01:00:00Z", "", {"test_timed_out": True})])
    assert read_for_head(candidate) == {}


def test_later_success_supersedes_old_timeout_regardless_of_insert_order(tmp_path):
    candidate = journal(tmp_path, [
        ("2026-09-06T02:00:00Z", "a" * 40, {"ok": True, "test_timed_out": False}),
        ("2026-09-06T01:00:00Z", "a" * 40, {"ok": False, "test_timed_out": True}),
    ])
    assert read_for_head(candidate)["ok"] is True
