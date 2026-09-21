"""Native record_pass receipts must not promote local PR blocks to host repair."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from test_issue_triage_fala import base_effector, run_graph

from lokay.fala_organ import _handle
from lokay.pass_history import read_pass_history
from lokay.pass_receipt import read_pass_receipt


@pytest.mark.parametrize("case", [
    "repair_start_product_dirt",
    "pr_repair_budget_exhausted",
    "published",
    "carrier",
])
def test_native_record_pass_to_both_recovery_selectors(tmp_path, monkeypatch, case):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state.jsonl"
    config = tmp_path / "config.yaml"
    config.write_text(f"state:\n  path: {state}\n")
    inputs = {"config_path": str(config)}
    identity = {
        "repo": "o/r", "pr": 9, "branch": "ai/fix/42-task",
        "repair_start_head_sha": "a" * 40,
    }
    blocked = case not in {"published", "carrier"}
    repair = {
        "ok": True,
        "route": "fail_closed" if blocked else "completed",
        **identity,
        **({"reason": case} if blocked else {
            "terminal": "publish", "published": True, "repaired": True,
            "head_sha": "b" * 40,
        }),
    }
    host_gate = ({"ok": True, "route": "blocked", "reason": "host_behind",
                  "error": "factory host source integrity failed"}
                 if case == "carrier" else {"ok": True, "route": "begin"})
    before = datetime(2026, 9, 21, tzinfo=UTC)
    for n in range(1, 6):
        # Replace only the clock and external department/host effects. Native
        # conduction, record_pass, persistence, terminal and both readers are real.
        timestamp = (before + timedelta(seconds=n)).isoformat()
        body = base_effector(f'''
from datetime import datetime
from lokay.fala_organ import _handle
from lokay.organ.common import _conduction_values
from lokay.proc import record_pass
class Clock:
    @staticmethod
    def now(tz):
        return datetime.fromisoformat({timestamp!r})
record_pass.datetime = Clock
up = _conduction_values(m)
if a == 'factory_begin_host_gate': v = {host_gate!r}
if a == 'factory_begin': v.update(state_path={str(state)!r})
if a.startswith('select_') and a.endswith('_department'): v.update(route='skip')
if a == 'select_pr_repair_department' and {blocked!r}:
    v = {repair!r}
if a == 'select_pr_repair_department' and {case == 'published'!r}:
    v.update(route='repair')
if a == 'run_pr_repair_department': v = {repair!r}
if a in {{'record_pass', 'factory_pass_terminal'}}:
    v = _handle(a, {inputs!r}, up)
''')
        native = run_graph(tmp_path, body, f"pass-{n}", path_id="factory_pass")
        assert native["effector_results"]["record_pass"]["status"] == "succeeded"
        receipt = read_pass_receipt(state_path=state)
        assert receipt is not None
        history = read_pass_history(state_path=state)
        assert len(history) == n
        assert len({row["ts"] for row in history}) == n
        if blocked:
            assert receipt["health"] == "pr_repair_blocked"
            assert receipt["reason"] == case
            assert receipt["ok"] is False
            assert receipt["progress"] == 0
            assert receipt["idle"] is False
            assert receipt["outcome"] == "none"
            for key, value in identity.items():
                assert receipt["pr_repair"][key] == value
        elif case == "published":
            assert receipt["health"] == "repairing"
            assert receipt["pr_repair"]["head_sha"] == "b" * 40
        else:
            assert receipt["health"] == "host_behind"
            assert receipt["ok"] is False
            assert receipt["error"] == host_gate["error"]
        persisted = json.dumps(history, sort_keys=True)
        daemon = _handle("select_repair_route", inputs, {})
        factory = _handle("select_self_repair_department", inputs, {})
        expected = ("repair", "run") if case == "carrier" and n == 5 else ("factory", "skip")
        assert (daemon["route"], factory["route"]) == expected, (daemon, factory)
        assert json.dumps(read_pass_history(state_path=state), sort_keys=True) == persisted
        assert read_pass_receipt(state_path=state) == receipt
