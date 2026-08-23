"""Survey scope: cold repos must not be walked every pass."""

from __future__ import annotations


import json

from lokay.passkit.hot import (
    load_last_pass_by_repo,
    pick_survey_repos,
    repo_is_hot,
    survey_scope,
)
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
    prev = {
        name: {"repo": name, "ready": 0, "inbox": 0, "open_ai_prs": 0} for name in repos
    }
    picked = pick_survey_repos(repos, prev, salt="all-cold", extra_cold=2)
    assert "mikolaj92/lokay" in picked
    assert len(picked) <= 3
    assert len(picked) < len(repos)


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


def test_pr_survey_slot_skips_cold_scope(tmp_path):
    from lokay.passkit import io as pass_io
    from lokay.proc.prepare_pr_survey import prepare
    from lokay.proc.select_pr_survey_slot import select

    pd = tmp_path / "pass"
    pd.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pd),
        {"repos": ["a/hot", "a/cold"], "survey_repos": ["a/hot"]},
    )
    pass_io.write_json(pass_io.working_path(pd), {})
    prepared = prepare(pass_dir=str(pd), slot_count=30)
    assert (
        select(prepared, slot=1)["route"] == "survey"
        and select(prepared, slot=2)["route"] == "cold"
    )


def test_survey_scope_none_means_all():
    assert survey_scope({"repos": ["a/one"]}) is None
    assert survey_scope({"survey_repos": ["a/one"]}) == ["a/one"]
