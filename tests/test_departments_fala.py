"""factory_pass parent: five named departments, independent switches."""

import tomllib
from pathlib import Path

from test_factory_pass_fala import _require_fala_host
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector

DEPARTMENTS = (
    "self_repair",
    "issue_triage",
    "executor",
    "pr_triage",
    "pr_repair",
)

SELECT = {
    "self_repair": "select_self_repair_department",
    "issue_triage": "select_issue_triage_department",
    "executor": "select_executor_department",
    "pr_triage": "select_pr_triage_department",
    "pr_repair": "select_pr_repair_department",
}

RUN = {
    "self_repair": "run_self_repair_department",
    "issue_triage": "run_issue_triage_department",
    "executor": "run_executor_department",
    "pr_triage": "run_pr_triage_department",
    "pr_repair": "run_pr_repair_department",
}


def _factory_path() -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == "factory_pass")


def simulate_departments(**routes: str) -> dict[str, str]:
    """Apply authored conduction + when. Default: sieves and executor on, repair off."""
    default = {
        "select_self_repair_department": "skip",
        "select_issue_triage_department": "run",
        "select_executor_department": "run",
        "select_pr_triage_department": "run",
        "select_pr_repair_department": "skip",
    }
    default.update(routes)
    status: dict[str, str] = {}
    pending = list(_factory_path()["effectors"])
    progressed = True
    while pending and progressed:
        progressed = False
        leftover = []
        for node in pending:
            deps = list(node.get("conduction") or [])
            if any(status.get(dep) not in {"succeeded", "skipped"} for dep in deps):
                leftover.append(node)
                continue
            when = dict(node.get("when") or {})
            name = str(node["id"])
            if when:
                upstream = str(when.get("upstream") or "")
                if status.get(upstream) != "succeeded" or default.get(upstream) != when.get(
                    "equals"
                ):
                    status[name] = "skipped"
                else:
                    status[name] = "succeeded"
            else:
                status[name] = "succeeded"
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def test_five_departments_are_parent_children() -> None:
    ids = [str(node["id"]) for node in _factory_path()["effectors"]]
    for name in DEPARTMENTS:
        assert SELECT[name] in ids, name
        assert RUN[name] in ids, name
    assert ids.index(SELECT["self_repair"]) < ids.index(SELECT["issue_triage"])
    assert ids.index(SELECT["issue_triage"]) < ids.index(SELECT["executor"])
    assert ids.index(SELECT["executor"]) < ids.index(SELECT["pr_triage"])
    assert ids.index(SELECT["pr_triage"]) < ids.index(SELECT["pr_repair"])
    assert "prs" not in ids
    assert "issues" not in ids


def test_issue_triage_without_executor() -> None:
    status = simulate_departments(select_executor_department="skip")
    assert status["run_issue_triage_department"] == "succeeded"
    assert status["run_executor_department"] == "skipped"
    assert status["run_pr_triage_department"] == "succeeded"
    assert status["record_pass"] == "succeeded"


def test_pr_triage_without_repair() -> None:
    status = simulate_departments(select_pr_repair_department="skip")
    assert status["run_pr_triage_department"] == "succeeded"
    assert status["run_pr_repair_department"] == "skipped"
    assert status["record_pass"] == "succeeded"


def test_executor_without_pr_triage() -> None:
    status = simulate_departments(select_pr_triage_department="skip")
    assert status["run_executor_department"] == "succeeded"
    assert status["run_pr_triage_department"] == "skipped"
    assert status["run_issue_triage_department"] == "succeeded"
    assert status["record_pass"] == "succeeded"


def test_disabling_executor_does_not_disable_either_sieve() -> None:
    status = simulate_departments(select_executor_department="skip")
    assert status["select_issue_triage_department"] == "succeeded"
    assert status["run_issue_triage_department"] == "succeeded"
    assert status["select_pr_triage_department"] == "succeeded"
    assert status["run_pr_triage_department"] == "succeeded"
    assert status["run_executor_department"] == "skipped"


def test_issue_triage_without_executor_native(tmp_path) -> None:
    _require_fala_host()
    body = base_effector(
        """if a=='factory_begin':v.update(pass_dir='/pass')
if a=='select_self_repair_department':v.update(route='skip',reason='last_pass_moved')
if a=='select_issue_triage_department':v.update(route='run')
if a=='run_issue_triage_department':v.update(ok=True,department='issue_triage')
if a=='select_executor_department':v.update(route='skip',reason='executor_disabled')
if a=='select_pr_triage_department':v.update(route='run')
if a=='run_pr_triage_department':v.update(ok=True,department='pr_triage')
if a=='select_pr_repair_department':v.update(route='skip',reason='pr_repair_disabled')
if a=='record_pass':v.update(result={'ok':True,'outcome':'none'})
if a=='factory_pass_terminal':v.update(result={'ok':True,'outcome':'none'})
if a=='reap_stale_worktrees':v.update(ok=True)"""
    )
    result = run_graph(tmp_path, body, "dept-triage", path_id="factory_pass")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["run_issue_triage_department"] == "succeeded"
    assert status["run_pr_triage_department"] == "succeeded"
    assert status["run_executor_department"] == "skipped"
    assert status["run_pr_repair_department"] == "skipped"
