"""Fail-closed harvest of finished detached issue_to_pr children into stuck.json."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from lokay.child_harvest import harvest_fail_closed_children
from lokay.stuck import excluded_numbers, load_stuck, stuck_path_for


def _receipt(path: Path, *, repo: str, issue: int, pid: int) -> None:
    path.write_text(
        json.dumps({"ok": True, "detached": True, "pid": pid, "repo": repo, "issue": issue}),
        encoding="utf-8",
    )


def _event(
    path: Path,
    *,
    repo: str,
    issue: int,
    ok: bool,
    reason: str | None = None,
    error: str | dict | None = None,
    run_id: str | None = None,
) -> None:
    ev: dict = {"kind": "issue_to_pr", "repo": repo, "issue": issue, "ok": ok}
    if reason is not None:
        ev["reason"] = reason
    if error:
        ev["error"] = error
    if run_id is not None:
        ev["run_id"] = run_id
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev) + "\n")


def test_dead_pid_fail_closed_reason_is_excluded(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    stuck_path = stuck_path_for(state)
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=999_999_999)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    stuck = load_stuck(stuck_path)
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#7"]
    assert row.get("blocked") is True
    assert row.get("reason") == "local_repair_exhausted"


def test_live_pid_does_not_block_even_with_fail_event(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=42)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda pid: int(pid) == 42,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_cycle_start_without_pid_does_not_block_live_sibling(tmp_path: Path):
    """Live 135: cycle_start (no pid) must not harvest a still-running detach."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "mikolaj92__lokay-135.json", repo="mikolaj92/lokay", issue=135, pid=42)
    (cycle / "mikolaj92__lokay__135.json").write_text(
        json.dumps({"repo": "mikolaj92/lokay", "issue": 135, "started_ts": "2026-08-15T15:15:15Z"}),
        encoding="utf-8",
    )
    _event(state, repo="mikolaj92/lokay", issue=135, ok=False, reason="invalid_branch_ref")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda pid: int(pid) == 42,
    )
    assert excluded_numbers(stuck, "mikolaj92/lokay") == set()


def test_ok_true_issue_closed_is_not_no_pr(tmp_path: Path):
    """A stopped/delivered child writes ok=True. That is not a vanished crash."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-5.json", repo="a/b", issue=5, pid=11)
    _event(state, repo="a/b", issue=5, ok=True, reason="issue_closed")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()
    assert stuck["issues"] == {}


def test_issue_closed_clears_stale_no_pr_row(tmp_path: Path):
    """Delivered tickets must not stay buried as vanished no_pr."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-5.json", repo="a/b", issue=5, pid=11)
    _event(state, repo="a/b", issue=5, ok=True, reason="issue_closed")
    stuck = {
        "issues": {
            "a/b#5": {
                "failures": 1,
                "blocked": True,
                "reason": "no_pr",
                "last_error": "issue_to_pr produced no PR",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()
    assert "a/b#5" not in stuck["issues"]


def test_github_closed_mill_issue_clears_stuck_without_journal(tmp_path: Path, monkeypatch):
    """Compacted state.jsonl still leaves CLOSED corpses; GitHub is the source of truth."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    stuck = {
        "issues": {
            "mikolaj92/lokay#528": {
                "failures": 1,
                "blocked": True,
                "reason": "no_pr",
                "last_error": "issue_to_pr produced no PR",
            },
            "mikolaj92/lokay#178": {
                "failures": 1,
                "blocked": True,
                "reason": "rebase_conflict",
            },
        }
    }

    def fake_closed(_repo: str) -> set[int]:
        return {528}

    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", fake_closed
    )
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert "mikolaj92/lokay#528" not in stuck["issues"]
    assert excluded_numbers(stuck, "mikolaj92/lokay") == {178}


def test_harvest_drops_out_of_scope_stuck_rows(tmp_path: Path, monkeypatch):
    """Mini mill must not keep Temida/test corpses on this host's ledger."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    stuck = {
        "issues": {
            "mikolaj92/lokay#178": {
                "failures": 1,
                "blocked": True,
                "reason": "rebase_conflict",
            },
            "mikolaj92/Temida#4094": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
            },
            "a/one#2": {
                "failures": 1,
                "blocked": True,
                "reason": "test_local_recheck_failed",
            },
        }
    }
    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", lambda _repo: set()
    )
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        repos=["mikolaj92/lokay"],
    )
    assert set(stuck["issues"]) == {"mikolaj92/lokay#178"}
    assert "mikolaj92/Temida#4094" in (stuck.get("cleared") or [])
    assert "a/one#2" in (stuck.get("cleared") or [])


def test_harvest_drops_toplevel_out_of_scope_stuck_rows(tmp_path: Path, monkeypatch):
    """Top-level Temida keys are still mill-ledger corpses, not issues[] rows."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    stuck = {
        "issues": {
            "mikolaj92/lokay#178": {
                "failures": 1,
                "blocked": True,
                "reason": "rebase_conflict",
            },
        },
        "mikolaj92/Temida#4805": {
            "reason": "plan_only",
            "blocked": True,
            "ts": "2026-08-18T22:43:45Z",
        },
        "mikolaj92/Temida#4806": {
            "reason": "plan_only",
            "blocked": True,
            "ts": "2026-08-18T22:43:45Z",
        },
    }
    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", lambda _repo: set()
    )
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        repos=["mikolaj92/lokay"],
    )
    assert set(stuck["issues"]) == {"mikolaj92/lokay#178"}
    assert "mikolaj92/Temida#4805" not in stuck
    assert "mikolaj92/Temida#4806" not in stuck
    assert "mikolaj92/Temida#4805" in (stuck.get("cleared") or [])
    assert "mikolaj92/Temida#4806" in (stuck.get("cleared") or [])


def test_harvest_without_repos_keeps_hermetic_rows(tmp_path: Path):
    """Harvest unit tests omit repos; do not wipe physics fixtures."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    stuck = {
        "issues": {
            "a/one#2": {
                "failures": 1,
                "blocked": True,
                "reason": "test_local_recheck_failed",
            },
            "a/two#2": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
            },
        },
        "a/one#9": {
            "reason": "plan_only",
            "blocked": True,
        },
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert set(stuck["issues"]) == {"a/one#2", "a/two#2"}
    assert "a/one#9" in stuck


def test_harvest_drops_out_of_scope_cycle_start_files(tmp_path: Path, monkeypatch):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    start = cycle / "mikolaj92__lokay__178.json"
    start.write_text(
        json.dumps(
            {
                "repo": "mikolaj92/lokay",
                "issue": 178,
                "started_ts": "2026-08-19T10:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    foreign = cycle / "mikolaj92__Temida__4094.json"
    foreign.write_text(
        json.dumps(
            {
                "repo": "mikolaj92/Temida",
                "issue": 4094,
                "started_ts": "2026-08-19T10:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    live = cycle / "mikolaj92__lokay-9.json"
    _receipt(live, repo="mikolaj92/lokay", issue=9, pid=12)
    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", lambda _repo: set()
    )
    harvest_fail_closed_children(
        {"issues": {}},
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: True,
        repos=["mikolaj92/lokay"],
    )
    assert start.exists()
    assert not foreign.exists()
    assert live.exists()


def test_harvest_drops_github_closed_mill_cycle_start_files(
    tmp_path: Path, monkeypatch
):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    closed = cycle / "mikolaj92__lokay__528.json"
    closed.write_text(
        json.dumps(
            {
                "repo": "mikolaj92/lokay",
                "issue": 528,
                "started_ts": "2026-08-19T10:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    open_start = cycle / "mikolaj92__lokay__178.json"
    open_start.write_text(
        json.dumps(
            {
                "repo": "mikolaj92/lokay",
                "issue": 178,
                "started_ts": "2026-08-19T10:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", lambda _repo: {528}
    )
    harvest_fail_closed_children(
        {"issues": {}},
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        repos=["mikolaj92/lokay"],
    )
    assert not closed.exists()
    assert open_start.exists()


def test_harvest_without_repos_keeps_cycle_start_files(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    start = cycle / "a__one__2.json"
    start.write_text(
        json.dumps({"repo": "a/one", "issue": 2, "started_ts": "2026-08-19T10:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    harvest_fail_closed_children(
        {"issues": {}},
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert start.exists()


def test_ok_true_without_pr_is_not_no_pr(tmp_path: Path):
    """ok=True and no PR is a stop/race, not FAIL_CLOSED no_pr."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-9.json", repo="a/b", issue=9, pid=12)
    _event(state, repo="a/b", issue=9, ok=True)
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()
    assert "a/b#9" not in stuck["issues"]


def test_dead_pid_without_event_or_reason_is_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    _receipt(cycle / "a__b-3.json", repo="a/b", issue=3, pid=1)
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 3 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#3"].get("reason") == "no_pr"


def test_dead_pid_with_pr_on_receipt_is_not_blocked(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    (cycle / "a__b-3.json").write_text(
        json.dumps({"ok": True, "detached": True, "pid": 1, "repo": "a/b", "issue": 3, "pr": 88}),
        encoding="utf-8",
    )
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_worktree_add_failed_error_is_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    _event(
        state,
        repo="a/b",
        issue=7,
        ok=False,
        error="worktree add failed:\nfatal: 'ai/fix/7-foo-..-bar' is not a valid branch name",
    )
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "invalid_branch_ref"


def test_nested_adapter_envelope_invalid_branch_is_fail_closed(tmp_path: Path):
    """Live SMT#7: top error is empty adapter_failed; reason sits in worktree_add."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "mikolaj92__ShowMeThePlayer-7.json", repo="mikolaj92/ShowMeThePlayer", issue=7, pid=8)
    nested = (
        "subprocess adapter failed: "
        '{"ok": false, "atom": "worktree_add", "error": '
        '"worktree reset-to-base failed:\\n'
        "Preparing worktree (new branch "
        "'ai/fix/7-uv.sources-pinuje-splot-na-..-splot-bez-ce23b5da')\\n"
        "fatal: 'ai/fix/7-uv.sources-pinuje-splot-na-..-splot-bez-ce23b5da' "
        'is not a valid branch name\\nhint: See \'git help check-ref-format\'\\n"}'
    )
    ev = {
        "kind": "issue_to_pr",
        "repo": "mikolaj92/ShowMeThePlayer",
        "issue": 7,
        "ok": False,
        "error": {"code": "adapter_failed", "message": "subprocess adapter failed: \n"},
        "terminal": {
            "pr_create": {
                "status": "failed",
                "error": {
                    "code": "adapter_failed",
                    "message": (
                        "subprocess adapter failed: "
                        '{"ok": false, "atom": "pr_create", '
                        '"error": "refusing: test_local_recheck did not succeed", '
                        '"reason": "test_local_recheck_failed"}'
                    ),
                },
            },
            "worktree_add": {
                "status": "failed",
                "error": {"code": "adapter_failed", "message": nested},
            },
        },
    }
    state.write_text(json.dumps(ev) + "\n", encoding="utf-8")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "mikolaj92/ShowMeThePlayer")
    assert stuck["issues"]["mikolaj92/ShowMeThePlayer#7"].get("reason") == "invalid_branch_ref"


def test_empty_jsonl_reason_falls_back_to_fala_journal_invalid_ref(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    ev = {
        "kind": "issue_to_pr",
        "repo": "a/b",
        "issue": 7,
        "ok": False,
        "error": {"code": "adapter_failed", "message": "subprocess adapter failed: \n"},
    }
    state.write_text(json.dumps(ev) + "\n", encoding="utf-8")
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    db = tmp_path / ".lokay" / "fala" / "i2pr" / "a__b__7" / "state.sqlite"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE processes (status TEXT, output_json TEXT, error_json TEXT, updated_at TEXT)"
    )
    con.execute(
        "INSERT INTO processes VALUES (?, ?, ?, ?)",
        ("failed", "{}", '{"message":"subprocess adapter failed: \\n"}', "2026-01-01T00:00:02Z"),
    )
    con.execute(
        "INSERT INTO processes VALUES (?, ?, ?, ?)",
        (
            "failed",
            "{}",
            '{"message":"fatal: \'ai/fix/7-foo-..-bar\' is not a valid branch name"}',
            "2026-01-01T00:00:01Z",
        ),
    )
    con.commit()
    con.close()
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        home=tmp_path,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "invalid_branch_ref"


def test_waiting_reason_is_not_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-4.json", repo="a/b", issue=4, pid=9)
    _event(state, repo="a/b", issue=4, ok=False, reason="checks_pending")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_issue_closed_is_not_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-5.json", repo="a/b", issue=5, pid=11)
    _event(state, repo="a/b", issue=5, ok=False, reason="issue_closed")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()
    assert stuck["issues"] == {}


def test_fala_journal_fallback_when_jsonl_silent(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    db = tmp_path / ".lokay" / "fala" / "i2pr" / "a__b__7" / "state.sqlite"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE processes (status TEXT, output_json TEXT, error_json TEXT, updated_at TEXT)"
    )
    con.execute(
        "INSERT INTO processes VALUES (?, ?, ?, ?)",
        ("failed", "{}", '{"message":"local_repair_exhausted"}', "2026-01-01T00:00:00Z"),
    )
    con.commit()
    con.close()
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        home=tmp_path,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "local_repair_exhausted"


def test_tmp_mill_does_not_inherit_host_cycle(tmp_path: Path):
    """A checkout mill with its own state.jsonl must not harvest host cycle."""
    host = tmp_path / "host"
    mill = tmp_path / "mill"
    host_cycle = host / ".lokay" / "cycle"
    host_cycle.mkdir(parents=True)
    mill.mkdir()
    _receipt(host_cycle / "a__one-2.json", repo="a/one", issue=2, pid=999_999_999)
    host_state = host / ".lokay" / "state.jsonl"
    host_state.parent.mkdir(parents=True, exist_ok=True)
    _event(host_state, repo="a/one", issue=2, ok=False, reason="test_local_recheck_failed")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=mill / "state.jsonl",
        home=host,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/one") == set()


def test_factory_begin_harvests_into_stuck(tmp_path: Path, monkeypatch):
    from lokay.proc.factory_begin import run_factory_begin

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state.jsonl"
    cycle = state.parent / "cycle"
    cycle.mkdir(parents=True)
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=999_999_999)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
github:
  assignee: t
repos:
  - name: a/b
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
state:
  path: {state}
""",
        encoding="utf-8",
    )
    out = run_factory_begin(config_path=str(cfg), live=False)
    assert out.get("ok") is True
    stuck = load_stuck(stuck_path_for(state))
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "local_repair_exhausted"


def test_harvest_indexes_state_jsonl_once_and_still_blocks(tmp_path: Path, monkeypatch):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    filler = json.dumps({"kind": "pass_receipt", "repo": "x/y", "issue": 1, "pad": "z" * 256})
    with state.open("w", encoding="utf-8") as fh:
        for i in range(3000):
            fh.write(filler + "\n")
        fh.write(
            json.dumps(
                {
                    "kind": "issue_to_pr",
                    "repo": "a/b",
                    "issue": 7,
                    "ok": False,
                    "reason": "local_repair_exhausted",
                }
            )
            + "\n"
        )
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    for n in range(8, 15):
        _receipt(cycle / f"a__b-{n}.json", repo="a/b", issue=n, pid=n)

    opens = {"n": 0}
    orig_open = Path.open

    def counting_open(self, *args, **kwargs):
        if self == state:
            opens["n"] += 1
        return orig_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)

    stuck = {"issues": {}}
    t0 = time.perf_counter()
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    dt = time.perf_counter() - t0
    assert opens["n"] == 1
    assert dt < 2.0
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "local_repair_exhausted"
    for n in range(8, 15):
        assert n in excluded_numbers(stuck, "a/b")
        assert stuck["issues"][f"a/b#{n}"].get("reason") == "no_pr"


def test_one_plan_only_already_blocked_stays_blocked(tmp_path: Path):
    """One plan_only leaves the slot; harvest must not reopen it."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-137.json", repo="a/b", issue=137, pid=8)
    _event(state, repo="a/b", issue=137, ok=False, reason="plan_only", run_id="run-1")
    stuck = {
        "issues": {
            "a/b#137": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
                "last_error": "plan_only",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 137 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#137"]
    assert row.get("blocked") is True
    assert row.get("failures") == 1
    assert row.get("reason") == "plan_only"


def test_three_plan_only_already_blocked_stays_blocked(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-137.json", repo="a/b", issue=137, pid=8)
    for i in range(1, 4):
        _event(state, repo="a/b", issue=137, ok=False, reason="plan_only", run_id=f"run-{i}")
    stuck = {
        "issues": {
            "a/b#137": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 137 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#137"]
    assert row.get("blocked") is True
    assert row.get("failures") == 1


def test_blocked_plan_only_without_cycle_dir_stays_blocked(tmp_path: Path):
    """One plan_only stays buried even when the cycle dir is missing."""
    state = tmp_path / "state.jsonl"
    _event(state, repo="a/b", issue=61, ok=False, reason="plan_only", run_id="run-1")
    stuck = {
        "issues": {
            "a/b#61": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=tmp_path / "missing-cycle",
        is_live=lambda _pid: False,
    )
    assert 61 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#61"].get("blocked") is True
    assert stuck["issues"]["a/b#61"].get("failures") == 1


def test_blocked_plan_only_without_receipt_stays_blocked(tmp_path: Path):
    """One plan_only stays buried even after the receipt is gone."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _event(state, repo="a/b", issue=61, ok=False, reason="plan_only", run_id="run-1")
    stuck = {
        "issues": {
            "a/b#61": {
                "failures": 1,
                "blocked": True,
                "reason": "plan_only",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 61 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#61"]
    assert row.get("blocked") is True
    assert row.get("failures") == 1


def test_fail_closed_already_blocked_is_not_incremented(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    _event(state, repo="a/b", issue=7, ok=False, reason="test_local_recheck_failed")
    stuck = {
        "issues": {
            "a/b#7": {
                "failures": 1,
                "blocked": True,
                "reason": "test_local_recheck_failed",
            }
        }
    }
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#7"]
    assert row.get("blocked") is True
    assert row.get("failures") == 1
    assert row.get("reason") == "test_local_recheck_failed"


def test_one_plan_only_leaves_the_slot(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-137.json", repo="a/b", issue=137, pid=8)
    _event(
        state,
        repo="a/b",
        issue=137,
        ok=False,
        reason=None,
        run_id="run-1",
        error={
            "code": "adapter_failed",
            "message": (
                'subprocess adapter failed: {"ok": false, '
                '"atom": "assert_real_diff", "reason": "plan_only"}'
            ),
        },
    )
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 137 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#137"]
    assert row.get("blocked") is True
    assert row.get("failures") == 1
    assert row.get("reason") == "plan_only"


def test_three_plan_only_run_ids_leave_the_slot(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-137.json", repo="a/b", issue=137, pid=8)
    for i in range(1, 4):
        _event(
            state,
            repo="a/b",
            issue=137,
            ok=False,
            reason="plan_only",
            run_id=f"run-{i}",
        )
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 137 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#137"]
    assert row.get("blocked") is True
    assert row.get("failures") == 3
    assert row.get("reason") == "plan_only"


def test_same_plan_only_event_reread_does_not_increment(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-137.json", repo="a/b", issue=137, pid=8)
    _event(
        state,
        repo="a/b",
        issue=137,
        ok=False,
        reason="plan_only",
        run_id="run-same",
    )
    stuck = {"issues": {}}
    for _ in range(10):
        harvest_fail_closed_children(
            stuck,
            state_path=state,
            cycle_dir=cycle,
            is_live=lambda _pid: False,
        )
    assert 137 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#137"].get("failures") == 1


def test_ok_breaks_trailing_plan_only_streak(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    _event(state, repo="a/b", issue=7, ok=False, reason="plan_only", run_id="a")
    _event(state, repo="a/b", issue=7, ok=False, reason="plan_only", run_id="b")
    _event(state, repo="a/b", issue=7, ok=True, run_id="ok")
    _event(state, repo="a/b", issue=7, ok=False, reason="plan_only", run_id="c")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("failures") == 1


def test_two_push_failed_leave_the_slot(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-86.json", repo="a/b", issue=86, pid=8)
    _event(state, repo="a/b", issue=86, ok=False, reason="push_failed", run_id="nff-1")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 86 not in excluded_numbers(stuck, "a/b")
    _event(state, repo="a/b", issue=86, ok=False, reason="push_failed", run_id="nff-2")
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 86 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#86"].get("failures") == 2



def test_one_rebase_conflict_does_not_leave_the_slot(tmp_path: Path):
    """Conflict close + re-ready is the product; harvest must not bury the retry."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-142.json", repo="a/b", issue=142, pid=1)
    _event(state, repo="a/b", issue=142, ok=False, reason="rebase_conflict", run_id="r1")
    stuck: dict = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 142 not in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#142"]
    assert row.get("blocked") is not True
    assert row.get("reason") == "rebase_conflict"


def test_three_rebase_conflicts_leave_the_slot(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-142.json", repo="a/b", issue=142, pid=1)
    for i in range(1, 4):
        _event(
            state,
            repo="a/b",
            issue=142,
            ok=False,
            reason="rebase_conflict",
            run_id=f"r{i}",
        )
    stuck: dict = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 142 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#142"].get("reason") == "rebase_conflict"


def test_terminal_influenzer_86_plan_only_row_with_zero_diff_error_is_not_refreshed(tmp_path: Path):
    """#86's recorded plan_only row and final zero_diff error stay terminal."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "mikolaj92__influenzer-86.json", repo="mikolaj92/influenzer", issue=86, pid=8)
    _event(
        state,
        repo="mikolaj92/influenzer",
        issue=86,
        ok=False,
        run_id="86-zero-diff",
        error={
            "code": "adapter_failed",
            "message": (
                'subprocess adapter failed: {"ok": false, "atom": "assert_real_diff", '
                '"error": "refusing: empty diff vs base; not progress", '
                '"reason": "zero_diff"}'
            ),
        },
    )
    stuck = {
        "issues": {
            "mikolaj92/influenzer#86": {
                "failures": 23,
                "blocked": True,
                "blocked_ts": "2026-08-16T12:31:39+00:00",
                "last_error": "refusing: empty diff vs base; not progress",
                "last_ts": "2026-08-16T12:31:39+00:00",
                "reason": "plan_only",
            }
        }
    }
    expected = json.loads(json.dumps(stuck))

    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )

    assert stuck == expected
    assert 86 in excluded_numbers(stuck, "mikolaj92/influenzer")


def test_terminal_influenzer_137_plan_only_is_not_refreshed(tmp_path: Path):
    """#137's final plan_only must remain a terminal skipped miss on each tick."""
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "mikolaj92__influenzer-137.json", repo="mikolaj92/influenzer", issue=137, pid=8)
    _event(
        state,
        repo="mikolaj92/influenzer",
        issue=137,
        ok=False,
        run_id="137-plan-only",
        error={
            "code": "adapter_failed",
            "message": (
                'subprocess adapter failed: {"ok": false, "atom": "assert_real_diff", '
                '"error": "refusing: diff is only plan/localize evidence", '
                '"reason": "plan_only"}'
            ),
        },
    )
    stuck = {
        "issues": {
            "mikolaj92/influenzer#137": {
                "failures": 72,
                "blocked": True,
                "blocked_ts": "2026-08-16T16:52:06+00:00",
                "last_error": "refusing: diff is only plan/localize evidence",
                "last_ts": "2026-08-16T16:52:06+00:00",
                "reason": "plan_only",
            }
        }
    }
    expected = json.loads(json.dumps(stuck))

    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )

    assert stuck == expected
    assert 137 in excluded_numbers(stuck, "mikolaj92/influenzer")



def test_journal_plan_only_without_receipt_or_stuck_row_leaves_the_slot(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _event(state, repo="a/b", issue=4796, ok=False, reason="plan_only", run_id="run-1")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 4796 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#4796"].get("reason") == "plan_only"


def test_harvest_idle_mill_stuck_drops_toplevel_temida(tmp_path: Path, monkeypatch):
    """Idle daemon_cycle skip still harvests mill stuck, including top-level keys."""
    from lokay.child_harvest import harvest_idle_mill_stuck

    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
mode: live
repos:
  - name: mikolaj92/Temida
    clone_path: {tmp_path / "Temida"}
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "lokay"}
state:
  path: {tmp_path / "state.jsonl"}
executor:
  enabled: false
""",
        encoding="utf-8",
    )
    (tmp_path / "state.jsonl").write_text("", encoding="utf-8")
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        json.dumps(
            {
                "issues": {
                    "mikolaj92/lokay#178": {
                        "failures": 1,
                        "blocked": True,
                        "reason": "rebase_conflict",
                    }
                },
                "mikolaj92/Temida#4805": {
                    "reason": "plan_only",
                    "blocked": True,
                    "ts": "2026-08-18T22:43:45Z",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lokay.child_harvest._github_closed_mill_issues", lambda _repo: set()
    )
    harvest_idle_mill_stuck(config_path=str(config), live=True)
    data = json.loads(stuck_path.read_text(encoding="utf-8"))
    assert set(data["issues"]) == {"mikolaj92/lokay#178"}
    assert "mikolaj92/Temida#4805" not in data


def test_harvest_idle_mill_stuck_skips_when_not_live(tmp_path: Path):
    from lokay.child_harvest import harvest_idle_mill_stuck

    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        json.dumps({"issues": {}, "mikolaj92/Temida#4805": {"blocked": True}})
        + "\n",
        encoding="utf-8",
    )
    harvest_idle_mill_stuck(config_path=str(tmp_path / "missing.yaml"), live=False)
    data = json.loads(stuck_path.read_text(encoding="utf-8"))
    assert "mikolaj92/Temida#4805" in data
