"""Autonomy certainty contracts — hermetic mill-pass canaries.

Pins product promises without live gh. Prefer policy atoms / pure functions /
envelopes. Where tick still owns scheduling until Fala extraction, assert the
public compose_tick surface that must remain.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lokay.compose import tick
from lokay.config import load_config
from lokay.intake import decide_intake
from lokay.merge_policy import decide_auto_merge
from lokay.models import Issue
from lokay.recovery_history import observe_run, record_observation, history_path_for

from fixtures.autonomy import (
    intake_ready_envelope,
    intake_reject_envelope,
    open_ai_pr,
    review_envelope,
    step_names,
    write_mill_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _issue(**kwargs) -> Issue:
    base = {
        "number": 1,
        "title": "Fix parser edge case",
        "body": "Handle empty input in parse().\n",
        "labels": [],
        "assignees": [],
        "state": "OPEN",
        "url": "https://example.test/1",
        "repo": "a/lib",
    }
    base.update(kwargs)
    return Issue(**base)


# ---------------------------------------------------------------------------
# 1) Busy repo A must not freeze clean repo B
# ---------------------------------------------------------------------------


def test_contract_busy_repo_a_does_not_block_clean_repo_b(tmp_path, monkeypatch):
    """Actionable AI PR in A: triage/implement still schedule in clean B."""
    config = write_mill_config(
        tmp_path,
        repos=("a/busy", "a/clean"),
        max_issue_to_pr_per_pass=2,
        max_triage_per_tick=5,
    )
    triage_calls: list[dict] = []
    implemented: list[dict] = []

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": [open_ai_pr(9)] if repo == "a/busy" else [],
            }
        if fn is tick.p_list_inbox.main:
            # Inbox only in clean repo — must still triage there.
            return {
                "ok": True,
                "issues": (
                    [{"number": 3, "repo": repo, "title": "inbox"}]
                    if repo == "a/clean"
                    else []
                ),
            }
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": (
                    [{"number": 2, "repo": repo, "title": "ready-work"}]
                    if repo == "a/clean"
                    else []
                ),
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        if fn is tick.p_intake.main:
            return intake_ready_envelope()
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "run_path",
        lambda **kw: triage_calls.append(kw) or {"ok": True},
    )
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or {"ok": True, "pr": 2, "branch": "ai/fix/2-ready-work"},
    )

    result = tick.compose_tick(config_path=config, live=True)

    assert any(c.get("repo") == "a/clean" for c in triage_calls)
    assert not any(c.get("repo") == "a/busy" for c in triage_calls)
    assert len(implemented) == 1
    assert implemented[0]["repo"] == "a/clean"
    steps = step_names(result["actions"])
    assert "skip_ready_open_ai_pr" in steps
    assert result["remaining"]["intake_skip_reason"] is None


# ---------------------------------------------------------------------------
# 2) K cap on issue_to_pr across repos
# ---------------------------------------------------------------------------


def test_contract_k_caps_issue_to_pr_across_repos(tmp_path, monkeypatch):
    repos = ("a/one", "a/two", "a/three", "a/four")
    config = write_mill_config(
        tmp_path, repos=repos, max_issue_to_pr_per_pass=3
    )
    implemented: list[dict] = []

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": f"work-{repo}"}],
            }
        if fn is tick.p_intake.main:
            return intake_ready_envelope()
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or {
            "ok": True,
            "pr": 10 + len(implemented),
            "branch": f"ai/fix/2-{kw['repo'].replace('/', '-')}",
        },
    )

    result = tick.compose_tick(config_path=config, live=True)

    assert len(implemented) == 3
    assert result["remaining"]["issue_to_pr_started"] == 3
    assert result["remaining"]["max_issue_to_pr_per_pass"] == 3
    by_repo = {row["repo"]: row for row in result["remaining"]["by_repo"]}
    # One clean repo must remain ready after K is exhausted.
    assert sum(1 for r in by_repo.values() if r.get("ready")) == 1


# ---------------------------------------------------------------------------
# 3) Soft waiting / repairing never counts as recovery stall fingerprint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("health", ["waiting", "repairing"])
def test_contract_soft_mill_health_never_stall_fingerprint(tmp_path, health):
    state = tmp_path / "state.jsonl"
    state.write_text(
        '{"kind":"pr_repair","ok":false,"error":"push rejected during repair"}\n',
        encoding="utf-8",
    )
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={"ok": True, "health": health, "progress": 0},
    )
    assert row["fingerprint"] is None
    assert row["evidence"] == ""

    history = history_path_for(state)
    for _ in range(5):
        assert record_observation(history, row) is None


def test_contract_soft_merge_policy_reasons_not_stall_evidence(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text(
        '{"kind":"pr_triage","ok":false,"reason":"checks_pending","waiting":true}\n',
        encoding="utf-8",
    )
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={"ok": True, "health": "waiting", "progress": 0},
    )
    assert row["fingerprint"] is None
    assert "checks_pending" not in (row.get("evidence") or "")


# ---------------------------------------------------------------------------
# 4) Intake CLOSE / SPLIT / READY gates implement
# ---------------------------------------------------------------------------


def test_contract_intake_ready_is_implementable(tmp_path: Path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="app"\n', encoding="utf-8")
    d = decide_intake(_issue(), clone_path=tmp_path, state="OPEN")
    assert d.decision == "ready"
    assert d.implementable is True


def test_contract_intake_close_not_implementable(tmp_path: Path):
    (tmp_path / "README.md").write_text("A pure library kit.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="kit"\n', encoding="utf-8")
    d = decide_intake(
        _issue(
            title="Adopt product_shell / Basecoat host stack",
            body="Wire product_shell and /static/platform for auth chrome.",
        ),
        clone_path=tmp_path,
        state="OPEN",
    )
    assert d.decision == "close"
    assert d.implementable is False


def test_contract_intake_split_not_implementable(tmp_path: Path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    d = decide_intake(
        _issue(
            title="Inventory everything across modules",
            body="Please inventory everything in the tree and list follow-ups.\n" * 2,
        ),
        clone_path=tmp_path,
    )
    assert d.decision == "split"
    assert d.implementable is False


@pytest.mark.parametrize(
    "decision,reason",
    [
        ("close", "wrong_product_shape"),
        ("split", "inventory_blob"),
    ],
)
def test_contract_intake_reject_gates_issue_to_pr(
    tmp_path, monkeypatch, decision, reason
):
    """Mill public surface: CLOSE/SPLIT under --require-ready never issue_to_pr."""
    config = write_mill_config(tmp_path, repos=("a/lib",), max_issue_to_pr_per_pass=1)
    implemented: list[dict] = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [
                    {
                        "number": 9,
                        "repo": "a/lib",
                        "title": "Work",
                        "labels": ["ai:ready"],
                    }
                ],
            }
        if fn is tick.p_intake.main:
            assert "--require-ready" in argv
            return intake_reject_envelope(decision, reason=reason)
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or (_ for _ in ()).throw(AssertionError("issue_to_pr must not run")),
    )

    result = tick.compose_tick(config_path=config, live=True)
    assert implemented == []
    assert "intake_issue" in step_names(result["actions"])


def test_contract_intake_ready_allows_issue_to_pr(tmp_path, monkeypatch):
    config = write_mill_config(tmp_path, repos=("a/lib",), max_issue_to_pr_per_pass=1)
    implemented: list[dict] = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 4, "repo": "a/lib", "title": "Fix parser"}],
            }
        if fn is tick.p_intake.main:
            assert "--require-ready" in argv
            return intake_ready_envelope()
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or {"ok": True, "pr": 7, "branch": "ai/fix/4-fix-parser"},
    )

    result = tick.compose_tick(config_path=config, live=True)
    assert len(implemented) == 1
    assert implemented[0]["issue_number"] == 4
    assert "intake_issue" in step_names(result["actions"])


# ---------------------------------------------------------------------------
# 5) merge_policy matrix smoke (pending / red / approve / secrets)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,action,reason",
    [
        (
            {
                "merge_enabled": True,
                "checks": {"status": "pending"},
                "review": review_envelope("approve"),
            },
            "waiting",
            "checks_pending",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "failed"},
                "review": review_envelope("approve"),
            },
            "repair",
            "checks_failed",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": review_envelope("approve"),
            },
            "merge",
            "approve_green",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": review_envelope("approve", secrets=True, merge_ok=False),
            },
            "blocked",
            "secrets",
        ),
    ],
)
def test_contract_merge_policy_matrix_smoke(kwargs, action, reason):
    got = decide_auto_merge(
        require_checks=True,
        require_llm_review=True,
        **kwargs,
    )
    assert got.action == action
    assert got.reason == reason
    if action == "waiting":
        assert got.waiting is True
    if action == "merge":
        assert got.merge_ok is True
    if reason == "secrets":
        assert got.needs_review is True


# ---------------------------------------------------------------------------
# Live autonomous profile (not the dry-run default)
# ---------------------------------------------------------------------------


def test_live_autonomous_example_profile_knobs():
    path = ROOT / "config.live-autonomous.example.yaml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["mode"] == "live"
    assert data["executor"]["enabled"] is True
    assert data["merge"]["enabled"] is True
    assert data["merge"]["require_checks"] is True
    assert data["merge"]["require_llm_review"] is True
    assert data["limits"]["max_issue_to_pr_per_pass"] == 3

    # Default example stays dry-run / merge-off (do not swap defaults).
    default = yaml.safe_load(
        (ROOT / "config.example.yaml").read_text(encoding="utf-8")
    )
    assert default["mode"] == "dry-run"
    assert default["executor"]["enabled"] is False
    assert default["merge"]["enabled"] is False

    # Profile must load (repos_file relative to config path).
    cfg = load_config(path)
    assert cfg.mode == "live"
    assert cfg.executor_enabled is True
    assert cfg.merge_enabled is True
    assert cfg.require_checks is True
    assert cfg.require_llm_review is True
    assert cfg.max_issue_to_pr_per_pass == 3
