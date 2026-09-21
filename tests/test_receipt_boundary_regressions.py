"""Factory conduction -> durable receipt -> next PR selection regressions."""

import pytest

from lokay.organ.factory import handle_factory
from lokay.pass_history import read_pass_history
from lokay.pass_receipt import read_pass_receipt, write_pass_receipt
from lokay.passkit import io as pass_io
from lokay.proc.select_next_pr import select
from lokay.proc.summarize_pr_triage_department import summarize
from lokay.proc.walk_pr_leftover import skipped_identity
from test_departments_fala import _factory_path
from test_record_pass import _begin

OLD, NEW = "a" * 40, "b" * 40
PR = {"repo": "acme/pr-repo", "pr": 84, "head_sha": OLD, "branch": "ai/fix/84"}
CTX = {"cfg": [], "live": [], "repo": "local/factory", "issue_number": None,
       "pr_number": None, "repair_mode": False, "branch": None}


def record(tmp_path, pass_dir, **departments):
    outputs = {"factory_begin": {"pass_dir": str(pass_dir)},
               "factory_begin_host_gate": {"route": "begin"}, **departments}
    node = next(n for n in _factory_path()["effectors"] if n["id"] == "record_pass")
    out = handle_factory("record_pass", {},
                         {key: outputs.get(key, {}) for key in node["conduction"]}, CTX)
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    terminal = handle_factory("factory_pass_terminal", {}, {"record_pass": out}, CTX)
    for key in ("ok", "outcome", "health", "progress", "idle", "remaining"):
        assert terminal["result"][key] == receipt[key]
    for key in ("pr_triage", "pr_repair", "reason"):
        assert terminal["result"].get(key) == receipt.get(key)
    assert read_pass_history(state_path=tmp_path / "state.jsonl")[0] == receipt
    return receipt


@pytest.mark.parametrize("case", ["worktree_failed", "repair_push_not_confirmed", "push", "transport_only", "same_sha", "missing_start", "missing_repo", "planned", "none", "merge"])
def test_independent_repair_evidence(tmp_path, case):
    pass_dir = _begin(tmp_path)
    pass_io.write_json(pass_io.tick_path(pass_dir),
                       {"health": "hosted", "idle": True, "lane": "idle", "progress": 0})
    triage = {**PR, "route": "completed", "verdict": "repair", "triage": {"merged": False}}
    repair = {}
    if case not in {"none", "merge"}:
        blocked = case in {"worktree_failed", "repair_push_not_confirmed"}
        child = {**PR, "terminal": "blocked" if blocked else "publish",
                 "reason": case if blocked else "", "repair_start_head_sha": OLD,
                 "head_sha": OLD if blocked else NEW,
                 "repaired": not blocked, "published": not blocked,
                 "findings": [{"body": "bulky evidence must not reach the small receipt"}]}
        repair = {"ok": True, "route": "fail_closed" if blocked else "completed",
                  "reason": case if blocked else "", "repair": {"ok": True, "result": child}}
        if case == "same_sha":
            child["head_sha"] = OLD
        elif case == "missing_start":
            child.pop("repair_start_head_sha")
        elif case == "missing_repo":
            child.pop("repo")
        elif case == "planned":
            repair["route"] = "planned"
        elif case == "transport_only":
            repair.pop("repair")
    if case == "merge":
        triage.update(verdict="merge", triage={"merged": True})
    receipt = record(tmp_path, pass_dir, run_pr_triage_department={"result": triage},
                     run_pr_repair_department=repair)
    assert receipt["outcome"] == ("merge" if case == "merge" else "none")
    assert receipt["pr_triage"]["verdict"] == triage["verdict"]
    assert receipt["pr_triage"]["repo"] == PR["repo"]
    if case in {"none", "merge"}:
        assert "pr_repair" not in receipt
        return
    evidence = receipt["pr_repair"]
    assert evidence["route"] == repair["route"]
    if case in {"transport_only", "same_sha", "missing_start", "missing_repo", "planned"}:
        assert receipt["progress"] == 0
        return
    assert (evidence["repo"], evidence["pr"], evidence["head_sha"]) == (
        PR["repo"], PR["pr"], NEW if case == "push" else OLD)
    assert "findings" not in evidence
    assert receipt["idle"] is False
    assert receipt["lane"] == "product"
    if case == "push":
        assert evidence["published"] is True
        assert receipt["progress"] == 1
        assert receipt["health"] == "repairing"
    else:
        assert receipt["ok"] is False
        assert receipt["health"] == "pr_repair_blocked"
        assert receipt["reason"] == case
        assert evidence["terminal"] == "blocked"
        assert evidence["published"] is False
        assert receipt["progress"] == 0
        # A second pass must keep the same named failure in history, not hosted/idle.
        record(tmp_path, pass_dir, run_pr_triage_department={"result": triage},
               run_pr_repair_department=repair)
        history = read_pass_history(state_path=tmp_path / "state.jsonl")
        assert [row["reason"] for row in history] == [case, case]


@pytest.mark.parametrize("issue_repo", ["acme/pr-repo", "acme/issue-repo"])
@pytest.mark.parametrize("fresh", [False, True])
def test_issue_skip_cannot_rewrite_pr_identity(tmp_path, issue_repo, fresh):
    pass_dir = _begin(tmp_path)
    prior = {"skipped_repo": PR["repo"], "skipped_pr": PR["pr"], "skipped_head_sha": OLD,
             "leftover_prs": []}
    write_pass_receipt({"remaining": prior}, state_path=tmp_path / "state.jsonl")
    selected_pr = {"repo": "acme/fresh-repo", "pr": 95, "head_sha": "c" * 40,
                   "branch": "ai/fix/95"} if fresh else PR
    prs = summarize({**selected_pr, "route": "pr", "leftover_prs": []}, {},
                    {"route": "skip", "reason": "manual"}, {"route": "review"}) if fresh else {}
    receipt = record(tmp_path, pass_dir, run_pr_triage_department=prs,
                     run_executor_department={"result": {"route": "skip", "repo": issue_repo, "issue": 42}})
    rem = receipt["remaining"]
    assert rem["skipped_issue_repo"] == issue_repo
    assert rem["skipped_issue"] == 42
    assert skipped_identity(rem) == (selected_pr["repo"], selected_pr["pr"], selected_pr["head_sha"])
    assert rem["skipped_pr_repo"] == selected_pr["repo"]
    assert select({"prs": [selected_pr]}, rem)["route"] == "none"
    changed = {**selected_pr, "head_sha": NEW}
    picked = select({"prs": [changed]}, rem)
    assert picked["head_sha"] == NEW
    assert picked["leftover_prs"] == []  # no duplicate new SHA
    # Empty selection and summary must carry the new tuple too.
    exhausted = select({"prs": [selected_pr]}, rem)
    summary = summarize(exhausted, {}, {}, {"route": "no_pr"})
    assert skipped_identity(summary) == skipped_identity(rem)


@pytest.mark.parametrize("legacy", [
    {"skipped_repo": "acme/issue-repo", "skipped_pr": 84, "skipped_head_sha": OLD, "skipped_issue": 42},
    {"skipped_repo": "acme/pr-repo", "skipped_pr": 84, "skipped_head_sha": OLD, "skipped_issue": 42},
    {"skipped_repo": "acme/pr-repo", "skipped_pr": 84},
    {"skipped_pr": 84, "skipped_head_sha": OLD},
])
def test_ambiguous_or_incomplete_legacy_is_not_inferred(tmp_path, legacy):
    pass_dir = _begin(tmp_path)
    write_pass_receipt({"remaining": legacy}, state_path=tmp_path / "state.jsonl")
    assert skipped_identity(legacy) is None
    receipt = record(tmp_path, pass_dir)
    assert skipped_identity(receipt["remaining"]) is None
    assert select({"prs": [PR]}, receipt["remaining"])["pr"] == 84


def test_partial_fresh_tuple_cannot_borrow_prior_components(tmp_path):
    pass_dir = _begin(tmp_path)
    write_pass_receipt({"remaining": {"skipped_repo": PR["repo"], "skipped_pr": 84,
                                      "skipped_head_sha": OLD}}, state_path=tmp_path / "state.jsonl")
    receipt = record(tmp_path, pass_dir, run_pr_triage_department={"skipped_pr": 95})
    assert skipped_identity(receipt["remaining"]) == (PR["repo"], 84, OLD)


@pytest.mark.parametrize("prior", [
    {"skipped_repo": "acme/issue-repo", "skipped_issue": 42},
    {"skipped_issue_repo": "acme/issue-repo", "skipped_issue": 42},
])
def test_issue_tuple_survives_pr_skip_and_incomplete_issue_skip(tmp_path, prior):
    pass_dir = _begin(tmp_path)
    write_pass_receipt({"remaining": prior}, state_path=tmp_path / "state.jsonl")
    receipt = record(tmp_path, pass_dir,
                     run_pr_triage_department={"skipped_repo": PR["repo"], "skipped_pr": 84,
                                               "skipped_head_sha": OLD},
                     run_executor_department={"route": "skip", "issue": 99})
    rem = receipt["remaining"]
    assert (rem["skipped_issue_repo"], rem["skipped_issue"]) == ("acme/issue-repo", 42)
    assert skipped_identity(rem) == (PR["repo"], 84, OLD)


def test_tick_and_prior_are_not_spliced_into_one_identity(tmp_path):
    pass_dir = _begin(tmp_path)
    write_pass_receipt({"remaining": {"skipped_repo": PR["repo"], "skipped_pr": 84,
                                      "skipped_head_sha": OLD}}, state_path=tmp_path / "state.jsonl")
    pass_io.write_json(pass_io.tick_path(pass_dir), {"remaining": {"skipped_pr": 95}})
    receipt = record(tmp_path, pass_dir)
    assert skipped_identity(receipt["remaining"]) == (PR["repo"], 84, OLD)
