"""Merged closing PR closeout removes readiness before another issue-to-PR run."""

from __future__ import annotations

import os
import time
from pathlib import Path
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
    assert out["pr"] == 41
    assert parked == [["--repo", "owner/repo", "--issue", "7"]]


def test_existing_merged_delivery_is_closed_out_before_graph_can_start(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(
        issue_to_pr,
        "load_config",
        lambda _path: SimpleNamespace(mode="live", state_path="state.jsonl"),
    )
    monkeypatch.setattr(issue_to_pr, "append_event", lambda *_a, **_k: None)
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
        config_path=None, repo="mikolaj92/lokay", issue_number=7, live=True
    )

    assert out["stopped"] is True
    assert out["closeout"]["labels_removed"] is True
    assert calls == [["--live", "--repo", "mikolaj92/lokay", "--issue", "7"]]



def test_leftover_closed_ready_parks_without_searching_prs(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [429])

    def boom(*_a, **_k):
        raise AssertionError("leftover closeout must not paginate mill PRs")

    monkeypatch.setattr(closeout, "find_pr_fixing_issue", boom)
    parked: list[list[str]] = []

    def run_proc(_main, argv):
        parked.append(argv)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "run_proc", run_proc)
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["closed_out"] == [{"repo": "mikolaj92/lokay", "issue": 429}]
    assert parked == [["--repo", "mikolaj92/lokay", "--issue", "429"]]


def test_leftover_skips_github_when_recent_empty_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)

    def boom(*_a, **_k):
        raise AssertionError("recent empty leftover must not list GitHub")

    monkeypatch.setattr(closeout, "closed_ready_numbers", boom)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["labels_removed"] is False
    assert out["closed_out"] == []


def test_pytest_does_not_skip_leftover_github_lists_using_the_mill_stamp(
    monkeypatch, tmp_path
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_leftover_github_lists_using_the_mill_stamp",
    )
    assert closeout.leftover_recently_empty(stamp) is False
    listed: list[str] = []
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=mill / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout, "closed_ready_numbers", lambda *_a, **_k: listed.append("gh") or []
    )
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out.get("skipped") is not True
    assert listed == ["gh", "gh"]
    hermetic = tmp_path / "leftover-closeout.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert closeout.leftover_recently_empty(hermetic) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Pytest must not skip leftover GitHub lists using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_probes_when_empty_stamp_expired(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out.get("skipped") is not True
    assert out["labels_removed"] is False
    assert stamp.is_file()
    assert stamp.stat().st_mtime >= old + closeout.LEFTOVER_TTL_SECONDS


def test_leftover_empty_probe_writes_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is False
    assert stamp.is_file()


def test_leftover_park_clears_empty_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [429])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout, "run_proc", lambda *_a, **_k: {"ok": True, "removed": True}
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["closed_out"] == [{"repo": "mikolaj92/lokay", "issue": 429}]
    assert not stamp.exists()


def test_leftover_closed_ready_with_merged_pr_strips_labels_without_i2pr(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[
                SimpleNamespace(name="mikolaj92/Temida"),
                SimpleNamespace(name="mikolaj92/lokay"),
                SimpleNamespace(name="mikolaj92/takt"),
            ],
            ready_label="ai:ready",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    surveyed: list[tuple[str, str]] = []

    def fake_closed_ready(_runner, repo, label, *, live):
        assert live is True
        surveyed.append((repo, label))
        return [7]

    monkeypatch.setattr(closeout, "closed_ready_numbers", fake_closed_ready)
    calls: list[dict[str, object]] = []

    def fake_park(*, repo, issue, allowed):
        calls.append({"repo": repo, "issue": issue, "allowed": allowed})
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "_park_ready", fake_park)
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["issue_to_pr_started"] == 0
    assert surveyed == [
        ("mikolaj92/lokay", "work:ready"),
        ("mikolaj92/lokay", "ai:ready"),
    ]
    assert calls == [
        {"repo": "mikolaj92/lokay", "issue": 7, "allowed": True}
    ]


def test_closed_ready_numbers_skips_product_repo_without_gh():
    class NoGhRunner:
        def run_checked(self, *_args, **_kwargs):
            raise AssertionError("product repo must not call gh")

    assert closeout.closed_ready_numbers(
        NoGhRunner(), "mikolaj92/Temida", "work:ready", live=True
    ) == []


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
