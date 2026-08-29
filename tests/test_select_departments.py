"""Parent department switches are independent (issue #892)."""

from lokay.proc.select_executor_department import select as select_executor
from lokay.proc.select_issue_triage_department import select as select_issue_triage
from lokay.proc.select_pr_repair_department import select as select_pr_repair
from lokay.proc.select_pr_triage_department import select as select_pr_triage
from lokay.proc.select_self_repair_department import select as select_self_repair


def test_self_repair_only_when_last_pass_did_not_move() -> None:
    assert select_self_repair(enabled=True, moved_forward=True) == {
        "ok": True,
        "route": "skip",
        "reason": "last_pass_moved",
    }
    assert select_self_repair(enabled=True, moved_forward=False)["route"] == "run"
    assert select_self_repair(
        enabled=True, moved_forward=False, receipt_present=False
    )["reason"] == "stale_receipt"
    assert select_self_repair(enabled=False, moved_forward=False) == {
        "ok": True,
        "route": "skip",
        "reason": "self_repair_disabled",
    }
    assert select_self_repair(
        enabled=True, moved_forward=False, leftover_skip=True
    ) == {
        "ok": True,
        "route": "skip",
        "reason": "leftover_skip",
    }


def test_issue_triage_switch_does_not_mention_executor() -> None:
    assert select_issue_triage(enabled=True)["route"] == "run"
    out = select_issue_triage(enabled=False)
    assert out["route"] == "skip"
    assert out["reason"] == "issue_triage_disabled"


def test_executor_switch_is_independent_of_sieves() -> None:
    assert select_executor(enabled=True)["route"] == "run"
    assert select_executor(enabled=False) == {
        "ok": True,
        "route": "skip",
        "reason": "executor_disabled",
    }
    assert select_issue_triage(enabled=True)["route"] == "run"
    assert select_pr_triage(enabled=True)["route"] == "run"


def test_pr_triage_switch_does_not_start_repair() -> None:
    assert select_pr_triage(enabled=True)["route"] == "run"
    assert select_pr_triage(enabled=False)["reason"] == "pr_triage_disabled"
    assert select_pr_repair({}, enabled=True, triage_ran=True) == {
        "ok": True,
        "route": "skip",
        "reason": "already_conducted_in_pr_triage",
    }


def test_pr_repair_disabled_leaves_sieve() -> None:
    out = select_pr_repair(
        {"triage": {"repairable": True}},
        enabled=False,
        triage_ran=False,
    )
    assert out["route"] == "skip"
    assert out["reason"] == "pr_repair_disabled"


def test_department_switches_load_independently(tmp_path, monkeypatch) -> None:
    from lokay.config import department_enabled, load_config

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """mode: dry-run
repos:
  - name: o/r
    clone_path: /tmp/r
    enabled: true
departments:
  self_repair: true
  issue_triage: true
  executor: false
  pr_triage: true
  pr_repair: false
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("LOKAY_DEPARTMENT_EXECUTOR", raising=False)
    monkeypatch.delenv("LOKAY_DEPARTMENT_PR_TRIAGE", raising=False)
    cfg = load_config(cfg_path)
    assert department_enabled(cfg, "issue_triage") is True
    assert department_enabled(cfg, "pr_triage") is True
    assert department_enabled(cfg, "executor") is False
    assert department_enabled(cfg, "pr_repair") is False
