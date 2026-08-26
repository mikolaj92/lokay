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


def _pass_workspace(tmp_path, repos, scope):
    from lokay.passkit import io as pass_io

    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.begin_path(path),
        {"repos": list(repos), "survey_repos": list(scope), "stuck": {"issues": {}}},
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "progress": 0,
            "survey_errors": 0,
            "prs_by_repo": {},
            "inbox_by_repo": {},
            "inbox_issues_by_repo": {},
            "stuck": {"issues": {}},
        },
    )
    return path


def test_cold_dual_ready_is_surveyed_not_skip_cold(tmp_path, monkeypatch):
    from lokay.passkit import io as pass_io
    from lokay.proc.inbox_survey_catalog import run as run_inbox
    from lokay.proc.ready_survey_catalog import run as run_ready

    repos = ["mikolaj92/lokay", "mikolaj92/app-factory"]
    path = _pass_workspace(tmp_path, repos, ["mikolaj92/lokay"])
    monkeypatch.setattr(
        "lokay.proc.list_dual_ready_issues.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "listed",
            "issues": (
                [{"number": 64, "labels": ["work:ready", "ai:ready"]}]
                if selected["repo"] == "mikolaj92/app-factory"
                else []
            ),
        },
    )
    listed_inbox = []
    monkeypatch.setattr(
        "lokay.proc.list_inbox_repo_issues.fetch",
        lambda selected, **kwargs: listed_inbox.append(selected["repo"])
        or {
            **selected,
            "ok": True,
            "route": "listed",
            "issues": [],
            "listed": {"ok": True, "issues": []},
        },
    )
    listed_ready = []
    monkeypatch.setattr(
        "lokay.proc.list_work_ready_issues.fetch",
        lambda selected, **kwargs: listed_ready.append(selected["repo"])
        or {
            "ok": True,
            "route": "listed",
            "repo": selected["repo"],
            "issues": (
                [{"number": 64, "labels": ["work:ready", "ai:ready"]}]
                if selected["repo"] == "mikolaj92/app-factory"
                else []
            ),
        },
    )
    inbox_prepared = {
        "ok": True,
        "repos": repos,
        "mini_repo": "mikolaj92/lokay",
        "skipped_repos": [],
        "active_repos": ["mikolaj92/lokay"],
        "scoped": True,
        "stuck": {"issues": {}},
        "recent_empty": False,
    }
    inbox = run_inbox(
        inbox_prepared, pass_dir=str(path), config_path=None, live=False
    )
    inbox_actions = pass_io.read_json(pass_io.working_path(path)).get("actions") or []
    assert "mikolaj92/app-factory" in listed_inbox
    assert not any(
        row.get("step") == "skip_cold_repo" and row.get("repo") == "mikolaj92/app-factory"
        for row in inbox_actions
    )
    assert inbox["ok"] is True

    ready = run_ready(
        {
            "ok": True,
            "route": "survey",
            "repos": repos,
            "active_repos": ["mikolaj92/lokay"],
            "skipped_repos": [],
            "recent_empty": False,
        },
        pass_dir=str(path),
        config_path=None,
        live=False,
    )
    ready_actions = pass_io.read_json(pass_io.working_path(path)).get("actions") or []
    assert "mikolaj92/app-factory" in listed_ready
    assert ready["remaining_ready"] == 1
    assert not any(
        row.get("step") == "skip_cold_repo" and row.get("repo") == "mikolaj92/app-factory"
        for row in ready_actions
    )


def test_empty_cold_repos_stay_skipped_without_30_slot_balloon(tmp_path, monkeypatch):
    from lokay.passkit import io as pass_io
    from lokay.proc.inbox_survey_catalog import run as run_inbox
    from lokay.proc.ready_survey_catalog import run as run_ready

    repos = ["mikolaj92/lokay", *(f"mikolaj92/product-{i}" for i in range(29))]
    path = _pass_workspace(tmp_path, repos, ["mikolaj92/lokay"])
    probed = []
    monkeypatch.setattr(
        "lokay.proc.list_dual_ready_issues.fetch",
        lambda selected, **kwargs: probed.append(selected["repo"])
        or {**selected, "ok": True, "route": "listed", "issues": []},
    )
    listed_inbox = []
    monkeypatch.setattr(
        "lokay.proc.list_inbox_repo_issues.fetch",
        lambda selected, **kwargs: listed_inbox.append(selected["repo"])
        or {
            **selected,
            "ok": True,
            "route": "listed",
            "issues": [],
            "listed": {"ok": True, "issues": []},
        },
    )
    listed_ready = []
    monkeypatch.setattr(
        "lokay.proc.list_work_ready_issues.fetch",
        lambda selected, **kwargs: listed_ready.append(selected["repo"])
        or {
            "ok": True,
            "route": "listed",
            "repo": selected["repo"],
            "issues": [],
        },
    )
    inbox = run_inbox(
        {
            "ok": True,
            "repos": repos,
            "mini_repo": "mikolaj92/lokay",
            "skipped_repos": [],
            "active_repos": ["mikolaj92/lokay"],
            "scoped": True,
            "stuck": {"issues": {}},
            "recent_empty": False,
        },
        pass_dir=str(path),
        config_path=None,
        live=False,
    )
    ready = run_ready(
        {
            "ok": True,
            "route": "survey",
            "repos": repos,
            "active_repos": ["mikolaj92/lokay"],
            "skipped_repos": [],
            "recent_empty": False,
        },
        pass_dir=str(path),
        config_path=None,
        live=False,
    )
    working = pass_io.read_json(pass_io.working_path(path))
    actions = list(working.get("actions") or [])
    cold = [name for name in repos if name != "mikolaj92/lokay"]
    assert listed_inbox == ["mikolaj92/lokay"]
    assert listed_ready == ["mikolaj92/lokay"]
    assert set(probed) == set(cold)
    assert inbox["remaining_inbox"] == 0
    assert ready["remaining_ready"] == 0
    assert {
        (row.get("repo"), row.get("survey"))
        for row in actions
        if row.get("step") == "skip_cold_repo"
    } == {(name, survey) for name in cold for survey in ("inbox", "ready")}
    assert len(repos) == 30
    assert len(actions) < 394
