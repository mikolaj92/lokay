"""Hermetic coverage for PR review head-SHA dedupe and request_changes escalation."""

from __future__ import annotations

import json

from lokay.pr_review import format_review_marker
from lokay.proc import pr_review as pr_review_mod
from lokay.runner import CommandResult, CommandSpec


def _cfg(tmp_path, *, max_rc: int = 2) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_llm_review: true
limits:
  max_request_changes_per_pr: {max_rc}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return str(path)


class _FakeRunner:
    def __init__(self, view: dict, *, comments_posted: list | None = None):
        self.view = view
        self.comments_posted = comments_posted if comments_posted is not None else []
        self.labels: list[str] = []

    def run_checked(self, spec: CommandSpec, *, live: bool):
        argv = list(spec.argv)
        if "view" in argv:
            return CommandResult(
                spec=spec,
                executed=True,
                returncode=0,
                stdout=json.dumps(self.view),
            )
        if "comment" in argv:
            body = argv[argv.index("--body") + 1]
            self.comments_posted.append(body)
            return CommandResult(spec=spec, executed=True, returncode=0, stdout="")
        if "edit" in argv and "--add-label" in argv:
            self.labels.append(argv[argv.index("--add-label") + 1])
            return CommandResult(spec=spec, executed=True, returncode=0, stdout="")
        if "label" in argv or "api" in argv:
            return CommandResult(spec=spec, executed=True, returncode=0, stdout="")
        return CommandResult(spec=spec, executed=True, returncode=0, stdout="")

    def run(self, spec: CommandSpec, *, live: bool):
        return CommandResult(spec=spec, executed=True, returncode=0, stdout="")


def test_same_head_skips_llm_and_does_not_repost(tmp_path, monkeypatch, capsys):
    marker = format_review_marker(
        head_sha="deadbeef01", verdict="request_changes", merge_ok=False
    )
    view = {
        "title": "x",
        "body": "y",
        "headRefName": "ai/fix/1-x",
        "headRefOid": "deadbeef01",
        "comments": [{"body": f"{marker}\n## Lokay LLM PR review"}],
    }
    runner = _FakeRunner(view)
    agent_calls = []

    monkeypatch.setattr(pr_review_mod, "runner", lambda: runner)
    monkeypatch.setattr(pr_review_mod, "agent_execute_allowed", lambda *a, **k: True)
    monkeypatch.setattr(pr_review_mod, "mutations_allowed", lambda *a, **k: True)
    monkeypatch.setattr(
        pr_review_mod,
        "run_agent",
        lambda *a, **k: agent_calls.append(1) or {"status": "ok", "stdout_tail": "{}"},
    )
    monkeypatch.setattr(pr_review_mod, "ensure_labels", lambda *a, **k: None)
    monkeypatch.setattr(pr_review_mod, "add_pr_labels", lambda *a, **k: None)
    monkeypatch.setattr(
        pr_review_mod, "resolve_repo_clone", lambda *a, **k: tmp_path
    )

    code = pr_review_mod.main(
        ["--config", _cfg(tmp_path), "--live", "--repo", "a/b", "--pr", "7"]
    )
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0
    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["reason"] == "already_reviewed_head"
    assert out["merge_ok"] is False
    assert agent_calls == []
    assert runner.comments_posted == []


def test_request_changes_cap_escalates_to_needs_review(tmp_path, monkeypatch, capsys):
    prior = format_review_marker(
        head_sha="1111111111111111111111111111111111111111",
        verdict="request_changes",
        merge_ok=False,
    )
    view = {
        "title": "x",
        "body": "y",
        "headRefName": "ai/fix/1-x",
        "headRefOid": "2222222222222222222222222222222222222222",
        "comments": [{"body": prior}],
    }
    runner = _FakeRunner(view)
    labels_added: list[str] = []

    monkeypatch.setattr(pr_review_mod, "runner", lambda: runner)
    monkeypatch.setattr(pr_review_mod, "agent_execute_allowed", lambda *a, **k: True)
    monkeypatch.setattr(pr_review_mod, "mutations_allowed", lambda *a, **k: True)
    monkeypatch.setattr(
        pr_review_mod,
        "run_agent",
        lambda *a, **k: {
            "status": "ok",
            "stdout_tail": (
                '{"verdict":"request_changes","secrets":false,"blocking":["again"],'
                '"summary":"still broken","scope_ok":true,"tests_adequate":true}'
            ),
        },
    )
    monkeypatch.setattr(pr_review_mod, "ensure_labels", lambda *a, **k: None)

    def _add_labels(r, repo, pr, labels, *, live):
        labels_added.extend(labels)

    monkeypatch.setattr(pr_review_mod, "add_pr_labels", _add_labels)
    monkeypatch.setattr(
        pr_review_mod, "resolve_repo_clone", lambda *a, **k: tmp_path
    )

    code = pr_review_mod.main(
        ["--config", _cfg(tmp_path, max_rc=2), "--live", "--repo", "a/b", "--pr", "7"]
    )
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0
    assert out["ok"] is True
    assert out["escalated"] is True
    assert out["merge_ok"] is False
    assert "ai:needs-review" in labels_added
    assert "ai:request-changes" not in labels_added
    assert runner.comments_posted
    assert "Escalation" in runner.comments_posted[0]


def test_tick_escalated_review_is_manual_not_repair(tmp_path, monkeypatch):
    from lokay.compose import tick

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_checks: false
limits:
  max_triage_per_tick: 0
  max_issues_per_tick: 0
  max_repairs_per_tick: 1
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": [
                    {
                        "number": 9,
                        "head_ref": "ai/fix/9-x",
                        "mergeable": "MERGEABLE",
                    }
                ],
            }
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            return {"ok": True, "issues": []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        raise AssertionError(fn)

    repair_calls = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_pr_triage",
        lambda **_: {
            "ok": True,
            "skipped": True,
            "repairable": False,
            "escalated": True,
            "reason": "llm_review_escalated_needs_review",
            "review": {"verdict": "request_changes", "secrets": False},
        },
    )
    monkeypatch.setattr(
        tick,
        "compose_pr_repair",
        lambda **kw: repair_calls.append(kw) or {"ok": True},
    )
    result = tick.compose_tick(config_path=str(cfg_path), live=True)
    assert repair_calls == []
    assert result["remaining"]["needs_repair"] == 0
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert result["remaining"]["review_limbo"] == 1
    assert result["health"] in {"waiting", "idle"} or result["ok"] is True
