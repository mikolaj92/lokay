"""Merged closing PR closeout removes readiness before another issue-to-PR run."""

from __future__ import annotations

from types import SimpleNamespace

import lokay.compose.issue_to_pr as issue_to_pr
from lokay.compose import mill as mill_mod
from lokay.proc import closeout


def test_open_issue_with_merged_fixes_pr_removes_ready_labels(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(config_path=None),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout,
        "find_pr_fixing_issue",
        lambda _runner, _repo, _issue, live, merged_only: {
            "number": 41,
            "state": "closed",
            "merged_at": "2026-08-20T10:00:00Z",
            "body": "Fixes #7",
        },
    )
    parked: list[list[str]] = []

    def run_proc(_main, argv):
        parked.append(argv)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "run_proc", run_proc)

    out = closeout.run_closeout(
        repo="owner/repo", issue=7, config_path=None, live=True
    )

    assert out["delivered"] is True
    assert out["labels_removed"] is True
    assert parked == [["--repo", "owner/repo", "--issue", "7"]]


def test_existing_merged_delivery_is_closed_out_before_graph_can_start(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(
        issue_to_pr, "load_config", lambda _path: SimpleNamespace(mode="live")
    )
    monkeypatch.setattr(
        issue_to_pr, "_delivery_stop_reason", lambda _repo, _issue: "delivery_pr_exists"
    )
    calls: list[list[str]] = []

    def run_proc(_main, argv):
        calls.append(argv)
        return {"ok": True, "delivered": True, "labels_removed": True}

    monkeypatch.setattr(issue_to_pr, "run_proc", run_proc)
    monkeypatch.setattr(
        issue_to_pr,
        "run_path",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("second i2pr must not start")),
    )

    out = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=7, live=True
    )

    assert out["stopped"] is True
    assert out["closeout"]["labels_removed"] is True
    assert calls == [["--live", "--repo", "owner/repo", "--issue", "7"]]



def test_leftover_closed_ready_with_merged_pr_strips_labels_without_i2pr(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="owner/repo")],
            ready_label="ai:ready",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout, "closed_ready_numbers", lambda *_args, **_kwargs: [7]
    )
    calls: list[dict[str, object]] = []

    def fake_closeout(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "delivered": True, "labels_removed": True, "pr": 41}

    monkeypatch.setattr(closeout, "run_closeout", fake_closeout)
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["issue_to_pr_started"] == 0
    assert calls == [
        {"repo": "owner/repo", "issue": 7, "config_path": None, "live": True}
    ]


def test_mill_tick_leftover_closed_ready_does_not_start_i2pr(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "mode: live",
                "repos:",
                "  - name: owner/repo",
                "    clone_path: /tmp",
                "executor:",
                "  enabled: true",
                "  agent: grok",
                "  command: grok",
                "  args: ['prompt']",
                "merge:",
                "  enabled: true",
                "  require_checks: false",
                "worktrees:",
                "  root: /tmp/wt",
                "state:",
                "  path: /tmp/state.jsonl",
                "",
            ]
        ),
        encoding="utf-8",
    )
    leftover_calls: list[dict[str, object]] = []

    def fake_leftover(**kwargs):
        leftover_calls.append(kwargs)
        return {
            "ok": True,
            "labels_removed": True,
            "issue_to_pr_started": 0,
            "leftover_closed": 1,
        }

    def fake_pass(**_kwargs):
        return {
            "ok": True,
            "idle": True,
            "health": "idle",
            "progress": 0,
            "remaining": {
                "inbox": 0,
                "ready": 0,
                "issue_to_pr_started": 0,
                "open_ai_prs": 0,
                "mergeable_green": 0,
                "merge_disabled": 0,
                "needs_repair": 0,
                "no_checks_blocked": 0,
                "merge_conflicts": 0,
                "survey_errors": 0,
            },
        }

    monkeypatch.setattr(mill_mod, "closeout_leftover_ready", fake_leftover)
    monkeypatch.setattr(mill_mod, "compose_factory_pass", fake_pass)
    monkeypatch.setattr(mill_mod, "run_preflight", lambda *_a, **_k: {"ok": True})
    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=2)
    assert leftover_calls
    assert out["ok"] is True
    last = out.get("last") or (out.get("results") or [{}])[-1]
    remaining = last.get("remaining") or {}
    assert int(remaining.get("issue_to_pr_started") or 0) == 0
    assert leftover_calls[0]["live"] is True
