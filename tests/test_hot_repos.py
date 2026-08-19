"""Survey scope: cold repos must not be walked every pass."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lokay.passkit.hot import load_last_pass_by_repo, pick_survey_repos, repo_is_hot, survey_scope
from lokay.proc.factory_begin import run_factory_begin
from lokay.proc.survey_prs import run_survey_prs


def test_empty_row_is_cold():
    assert repo_is_hot({}) is False
    assert repo_is_hot({"inbox": 0, "ready": 0, "open_ai_prs": 0}) is False


def test_ready_or_pr_or_occupy_is_hot():
    assert repo_is_hot({"ready": 3}) is True
    assert repo_is_hot({"open_ai_prs": 1}) is True
    assert repo_is_hot({"occupied": True}) is True
    assert repo_is_hot({"survey_error": True}) is True


def test_pick_surveys_hot_plus_rotated_cold():
    repos = ["a/one", "a/two", "a/three", "a/four"]
    prev = {"a/two": {"repo": "a/two", "ready": 4, "inbox": 0, "open_ai_prs": 0}}
    first = pick_survey_repos(repos, prev, salt="p1", extra_cold=2)
    assert first[0] == "a/two"
    assert first[1] == "a/one"
    assert len(first) == 3
    second = pick_survey_repos(repos, prev, salt="p2", extra_cold=2)
    assert "a/two" in second
    assert set(first) != set(second) or first != second


def test_cold_survey_keeps_k_dispatch_lanes_in_config_order():
    repos = ["a/four", "a/one", "a/three", "a/two"]
    for salt in ("p1", "p2", "p3"):
        picked = pick_survey_repos(repos, {}, salt=salt, extra_cold=3)
        assert picked[:3] == ["a/four", "a/one", "a/three"]


def test_no_last_pass_surveys_anchor_plus_bounded_cold():
    repos = ["mikolaj92/lokay", *(f"mikolaj92/product-{i}" for i in range(28))]
    picked = pick_survey_repos(repos, {}, salt="empty", extra_cold=2)
    assert "mikolaj92/lokay" in picked
    assert len(picked) <= 3
    assert len(picked) < len(repos)


def test_all_cold_surveys_anchor_plus_bounded_cold():
    repos = ["mikolaj92/lokay", *(f"mikolaj92/product-{i}" for i in range(28))]
    prev = {name: {"repo": name, "ready": 0, "inbox": 0, "open_ai_prs": 0} for name in repos}
    picked = pick_survey_repos(repos, prev, salt="all-cold", extra_cold=2)
    assert "mikolaj92/lokay" in picked
    assert len(picked) <= 3
    assert len(picked) < len(repos)


def test_factory_begin_cold_survey_covers_configured_issue_budget(tmp_path, monkeypatch):
    repos = ["mikolaj92/lokay", "a/one", "a/two", "a/three"]
    cfg = SimpleNamespace(
        mode="dry_run",
        active_repos=lambda: [SimpleNamespace(name=name) for name in repos],
        agent="agent",
        state_path=tmp_path / "state.jsonl",
        config_path=None,
        max_triage_per_tick=0,
        max_issue_to_pr_per_pass=3,
        max_repairs_per_tick=0,
        max_failures_before_block=1,
        executor_enabled=False,
        merge_enabled=False,
        require_checks=True,
        require_llm_review=False,
        ready_label="work:ready",
        blocked_label="ai:blocked",
        branch_prefix="ai/",
    )
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr("lokay.proc.factory_begin.load_cfg", lambda _args: cfg)
    monkeypatch.setattr("lokay.proc.factory_begin.harvest_fail_closed_children", lambda *_args, **_kwargs: None)

    result = run_factory_begin(config_path=None, live=False)

    assert result["ok"] is True
    begin = json.loads((Path(result["pass_dir"]) / "begin.json").read_text(encoding="utf-8"))
    assert len(begin["survey_repos"]) >= cfg.max_issue_to_pr_per_pass
    assert set(begin["survey_repos"]) == set(repos)


def test_load_last_pass_by_repo(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    (tmp_path / "last-pass.json").write_text(
        json.dumps(
            {
                "remaining": {
                    "by_repo": [
                        {"repo": "a/hot", "ready": 2, "inbox": 0, "open_ai_prs": 0},
                        {"repo": "a/cold", "ready": 0, "inbox": 0, "open_ai_prs": 0},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    by_repo = load_last_pass_by_repo(state)
    assert repo_is_hot(by_repo["a/hot"]) is True
    assert repo_is_hot(by_repo["a/cold"]) is False


def test_survey_prs_skips_cold_scope(tmp_path, monkeypatch):
    from lokay.passkit import io as pass_io

    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["a/hot", "a/cold"],
            "survey_repos": ["a/hot"],
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "survey_errors": 0},
    )
    called: list[str] = []

    def fake_run(fn, argv):
        called.append(argv[argv.index("--repo") + 1])
        return {"ok": True, "prs": [{"number": 1}]}

    monkeypatch.setattr("lokay.proc.survey_prs.run_proc", fake_run)
    out = run_survey_prs(pass_dir=str(pass_dir), config_path=None, live=True)
    assert out["ok"] is True
    assert called == ["a/hot"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["prs_by_repo"]["a/hot"] == [{"number": 1}]
    assert working["prs_by_repo"]["a/cold"] == []
    assert any(a.get("step") == "skip_cold_repo" and a.get("repo") == "a/cold" for a in working["actions"])


def test_survey_scope_none_means_all():
    assert survey_scope({"repos": ["a/one"]}) is None
    assert survey_scope({"survey_repos": ["a/one"]}) == ["a/one"]
