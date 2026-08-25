"""Contracts for minimal ready-survey Unix processes."""

from lokay.passkit import io as pass_io


def workspace(tmp_path, *, repos=("a/one",), scope=None):
    path = tmp_path / "pass"
    path.mkdir()
    begin = {"repos": list(repos), "branch_prefix": "ai/fix/", "stuck": {"issues": {}}}
    if scope is not None:
        begin["survey_repos"] = list(scope)
    pass_io.write_json(pass_io.begin_path(path), begin)
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


def test_prepare_and_select_expose_catalog_slots(tmp_path):
    from lokay.proc.prepare_ready_survey import prepare
    from lokay.proc.select_ready_repo_slot import select

    path = workspace(tmp_path, repos=("a/one", "a/two"), scope=("a/two",))
    prepared = prepare(pass_dir=str(path), slot_count=2)
    assert select(prepared, slot=1)["route"] == "cold"
    assert select(prepared, slot=2) == {
        "ok": True,
        "route": "survey",
        "slot": 2,
        "repo": "a/two",
    }
    assert select(prepared, slot=3)["route"] == "empty"


def test_classify_is_pure_and_closed(tmp_path):
    from lokay.proc.classify_ready_repo_issues import classify

    path = workspace(tmp_path)
    begin = pass_io.read_json(pass_io.begin_path(path))
    working = pass_io.read_json(pass_io.working_path(path))
    working["prs_by_repo"] = {"a/one": [{"head_ref": "ai/fix/7-x"}]}
    working["stuck"] = {"issues": {"a/one#8": {"blocked": True}}}
    pass_io.write_json(pass_io.working_path(path), working)
    result = classify(
        pass_dir=str(path),
        selected={"route": "survey", "repo": "a/one"},
        listed={
            "route": "listed",
            "issues": [{"number": 7}, {"number": 8}, {"number": 9}],
        },
    )
    assert result["route"] == "blocked"
    assert [x["number"] for x in result["covered"]] == [7]
    assert [x["number"] for x in result["blocked"]] == [8]
    assert [x["number"] for x in result["implementable"]] == [9]


def test_classify_excludes_human_stops_and_keeps_unlabeled(tmp_path):
    from lokay.proc.classify_ready_repo_issues import classify

    path = workspace(tmp_path)
    result = classify(
        pass_dir=str(path),
        selected={"route": "survey", "repo": "a/one"},
        listed={
            "route": "listed",
            "issues": [
                {"number": 1, "labels": []},
                {"number": 2, "labels": ["ai:blocked"]},
                {"number": 3, "labels": ["ai:needs-feedback"]},
                {"number": 4, "labels": ["frozen"]},
                {"number": 5, "labels": ["ai:ready"]},
            ],
        },
    )
    assert [x["number"] for x in result["implementable"]] == [1, 5]


def test_reduce_folds_inbox_only_unlabeled_into_ready(tmp_path):
    from lokay.proc.reduce_ready_survey import reduce_state

    path = workspace(tmp_path, repos=("mikolaj92/Temida",))
    working = pass_io.read_json(pass_io.working_path(path))
    working["inbox_issues_by_repo"] = {
        "mikolaj92/Temida": [{"number": 4968, "labels": [], "title": "inbox"}]
    }
    out = reduce_state(
        prepared={"skipped_repos": [], "recent_empty": False},
        working=working,
        results=[
            {
                "repo": "mikolaj92/Temida",
                "route": "record",
                "implementable": [],
                "covered": [],
            }
        ],
    )
    assert out["remaining_ready"] == 1
    assert out["ready_by_repo"]["mikolaj92/Temida"][0]["number"] == 4968


def test_finalize_only_materializes_reactions(tmp_path):
    from lokay.proc.finalize_ready_survey import finalize
    from lokay.proc.reduce_ready_survey import reduce_state

    path = workspace(tmp_path, repos=("a/one", "a/two"))
    working = pass_io.read_json(pass_io.working_path(path))
    reduced = reduce_state(
        prepared={"skipped_repos": [], "recent_empty": False},
        working=working,
        results=[
            {
                "repo": "a/one",
                "route": "record",
                "implementable": [{"number": 9}],
                "covered": [],
            },
            {"repo": "a/two", "route": "failed"},
        ],
    )
    out = finalize(pass_dir=str(path), reduced=reduced)
    survey = pass_io.read_json(pass_io.survey_path(path))
    assert out["remaining_ready"] == 1 and out["probe_failed"] is True
    assert survey["ready_by_repo"]["a/one"] == [{"number": 9}]
    assert survey["ready_survey_failed"] == ["a/two"]


def test_prepare_fails_closed_when_catalog_exceeds_authored_slots(tmp_path):
    from lokay.proc.prepare_ready_survey import prepare

    path = workspace(tmp_path, repos=("a/one", "a/two"))
    out = prepare(pass_dir=str(path), slot_count=1)
    assert out["ok"] is False
    assert out["error"] == "ready survey catalog exceeds authored slots"
