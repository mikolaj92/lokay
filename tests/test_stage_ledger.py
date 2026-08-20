"""Hermetic issue ledger stage transitions (no live gh)."""

from __future__ import annotations

import pytest

from lokay.stage_ledger import (
    LABEL_CI_WAITING,
    LABEL_IMPLEMENTING,
    LABEL_PR_OPEN,
    LABEL_READY,
    LABEL_REPAIRING,
    LEDGER_ACTIVE_LABELS,
    NEW_LEDGER_LABELS,
    current_ledger_stage,
    plan_stage_transition,
)
from lokay.triage import decision_labels, is_undecided


def test_new_ledger_labels_budget():
    assert NEW_LEDGER_LABELS == ()


def test_exclusive_ready_clears_in_flight():
    plan = plan_stage_transition("ready")
    assert plan.add_labels == (LABEL_READY,)
    assert LABEL_IMPLEMENTING in plan.remove_labels
    assert LABEL_PR_OPEN in plan.remove_labels
    assert LABEL_CI_WAITING in plan.remove_labels
    assert LABEL_REPAIRING in plan.remove_labels
    assert LABEL_READY not in plan.remove_labels


def test_inflight_stage_names_keep_ready():
    for name in ("implementing", "pr-open", "ci-waiting", "repairing"):
        plan = plan_stage_transition(name)
        assert plan.stage == "ready"
        assert plan.add_labels == (LABEL_READY,)
        assert LABEL_IMPLEMENTING in plan.remove_labels
        assert LABEL_PR_OPEN in plan.remove_labels
        assert LABEL_READY not in plan.remove_labels


def test_clear_strips_ready_and_cache():
    clear = plan_stage_transition("clear")
    assert clear.add_labels == ()
    assert set(clear.remove_labels) == {
        LABEL_READY,
        LABEL_IMPLEMENTING,
        LABEL_PR_OPEN,
        LABEL_CI_WAITING,
        LABEL_REPAIRING,
    }


def test_receipt_optional():
    assert plan_stage_transition("ready", receipt=False).receipt is None
    assert "ready" in (plan_stage_transition("ready", receipt=True).receipt or "")
    assert plan_stage_transition("implementing", receipt=True).receipt is not None


def test_unknown_stage_raises():
    with pytest.raises(ValueError, match="unknown ledger stage"):
        plan_stage_transition("nope")


def test_current_ledger_stage_prefers_repairing():
    assert (
        current_ledger_stage(
            [LABEL_READY, LABEL_PR_OPEN, LABEL_REPAIRING, LABEL_CI_WAITING]
        )
        == "repairing"
    )
    assert current_ledger_stage([LABEL_READY]) == "ready"
    assert current_ledger_stage([]) is None


def test_ledger_labels_leave_inbox():
    for label in LEDGER_ACTIVE_LABELS:
        assert not is_undecided([label])
        assert label in decision_labels()


def test_stage_label_atom_dry_run_envelope(tmp_path, monkeypatch, capsys):
    import json

    from lokay.proc import stage_label as atom
    from lokay.runner import CommandResult

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mode: dry-run
github:
  assignee: mikolaj92
repos: []
""",
        encoding="utf-8",
    )
    calls: list[tuple] = []

    class _R:
        def run(self, spec, *, live):
            calls.append((tuple(spec.argv), live))
            return CommandResult(spec=spec, executed=live, returncode=0)

        def run_checked(self, spec, *, live):
            return self.run(spec, live=live)

    monkeypatch.setattr(atom, "runner", lambda: _R())
    code = atom.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "7",
            "--stage",
            "implementing",
        ]
    )
    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["applied"] is False
    assert env["stage"] == "ready"
    assert env["add_labels"] == [LABEL_READY]
    assert LABEL_IMPLEMENTING in env["remove_labels"]
    assert LABEL_READY not in env["remove_labels"]
    # dry-run still plans through gh helpers with live=False
    assert calls and all(live is False for _, live in calls)


def test_stage_label_open_pr_keeps_both_ready_labels(tmp_path, monkeypatch, capsys):
    import json
    from types import SimpleNamespace

    from lokay.proc import stage_label as atom

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mode: live
github:
  assignee: mikolaj92
  ready_label: work:ready
repos: []
""",
        encoding="utf-8",
    )
    removed: list[str] = []
    added: list[str] = []
    monkeypatch.setattr(atom, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        atom,
        "plan_stage_transition",
        lambda *a, **k: SimpleNamespace(
            stage="pr-open",
            add_labels=(),
            remove_labels=("work:ready", LABEL_READY, LABEL_PR_OPEN),
            receipt=None,
        ),
    )
    monkeypatch.setattr(
        atom,
        "get_issue",
        lambda *a, **k: SimpleNamespace(state="OPEN"),
    )
    monkeypatch.setattr(
        atom,
        "remove_issue_labels",
        lambda runner, repo, issue, labels, *, live: removed.extend(labels),
    )
    monkeypatch.setattr(
        atom,
        "add_issue_labels",
        lambda runner, repo, issue, labels, *, live: added.extend(labels),
    )

    code = atom.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "7",
            "--stage",
            "pr-open",
        ]
    )

    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert added == []
    assert removed == [LABEL_PR_OPEN]
    assert "work:ready" not in env["remove_labels"]
    assert LABEL_READY not in env["remove_labels"]


def test_stage_label_clear_may_remove_ready_after_merge():
    from lokay.proc.stage_label import _open_issue_removals

    assert _open_issue_removals(
        ("work:ready", LABEL_READY),
        stage="clear",
        ready_label="work:ready",
    ) == ["work:ready", LABEL_READY]


def test_stage_label_live_missing_ci_waiting_does_not_abort(tmp_path, monkeypatch, capsys):
    import json

    from lokay.proc import stage_label as atom
    from lokay.runner import CommandResult

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mode: live
github:
  assignee: mikolaj92
repos: []
""",
        encoding="utf-8",
    )

    class _R:
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if "view" in argv:
                return CommandResult(
                    spec=spec,
                    executed=True,
                    returncode=0,
                    stdout=(
                        '{"number":7,"title":"test","body":"","labels":[],'
                        '"assignees":[],"url":"https://example.test/7",'
                        '"state":"OPEN"}'
                    ),
                )
            if "--remove-label" in argv:
                label = argv[argv.index("--remove-label") + 1]
                if label == LABEL_CI_WAITING:
                    return CommandResult(
                        spec=spec,
                        executed=True,
                        returncode=1,
                        stderr=(
                            "failed to update https://github.com/a/b/issues/7: "
                            f"'{LABEL_CI_WAITING}' not found\n"
                        ),
                    )
            return CommandResult(spec=spec, executed=True, returncode=0)

        def run_checked(self, spec, *, live):
            result = self.run(spec, live=live)
            if live and result.returncode != 0:
                raise RuntimeError(result.stderr)
            return result

    monkeypatch.setattr(atom, "runner", lambda: _R())
    monkeypatch.setattr(atom, "mutations_allowed", lambda **k: True)
    code = atom.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "7",
            "--stage",
            "implementing",
        ]
    )
    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["applied"] is True
    assert env["stage"] == "ready"


def test_stage_label_closed_issue_skips_all_mutations(
    tmp_path, monkeypatch, capsys
):
    import json
    from types import SimpleNamespace

    from lokay.proc import stage_label as atom

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mode: live
github:
  assignee: mikolaj92
repos: []
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(atom, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        atom,
        "get_issue",
        lambda *a, **k: SimpleNamespace(state="CLOSED"),
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("closed issue must not be mutated")

    monkeypatch.setattr(atom, "add_issue_labels", unexpected)
    monkeypatch.setattr(atom, "remove_issue_labels", unexpected)
    monkeypatch.setattr(atom, "comment_issue", unexpected)

    code = atom.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "7",
            "--stage",
            "ready",
            "--receipt",
        ]
    )

    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["skipped"] is True
    assert env["reason"] == "issue_closed"
    assert env["issue_state"] == "CLOSED"
    assert env["add_labels"] == []
    assert env["remove_labels"] == []
    assert env["receipt"] is False
    assert env["applied"] is False
