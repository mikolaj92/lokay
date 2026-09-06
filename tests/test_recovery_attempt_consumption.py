"""One repair attempt consumes earlier stall evidence, not future passes."""

import sqlite3
from types import SimpleNamespace

from lokay.fala_organ import _handle
from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import write_pass_receipt
from test_repair_quorum import receipt


def test_both_bindings_require_fresh_passes_after_repair(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state.jsonl"
    config = SimpleNamespace(state_path=state, department_self_repair=True)
    monkeypatch.setattr("lokay.config.load_config", lambda _: config)
    monkeypatch.setattr("lokay.proc._common.load_cfg", lambda _: config)
    monkeypatch.setattr("lokay.organ.departments_boundary._department_enabled", lambda *_: True)
    rows = [receipt(n) for n in range(1, 6)]
    for row in rows:
        append_pass_receipt(row, state_path=state)
    write_pass_receipt(rows[-1], state_path=state)
    folder = tmp_path / ".lokay/fala/self-repair"
    folder.mkdir(parents=True)
    with sqlite3.connect(folder / "state.sqlite") as conn:
        conn.execute("CREATE TABLE runs (id TEXT, correlation_path_id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, ?, ?)", ("repair-1", "self_repair", rows[-1]["ts"]))
    assert _handle("select_repair_route", {"config_path": "isolated.yaml"}, {})["route"] == "factory"
    assert _handle("select_self_repair_department", {"config_path": "isolated.yaml"}, {})["route"] == "skip"
    for n in range(6, 11):
        row = receipt(n)
        append_pass_receipt(row, state_path=state)
        write_pass_receipt(row, state_path=state)
    assert _handle("select_repair_route", {"config_path": "isolated.yaml"}, {})["route"] == "repair"
