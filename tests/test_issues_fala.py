"""Native Fala proofs: issues nests issue_row; issue_row is one implement."""

import os

import pytest
import tomllib
from pathlib import Path

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _path_raw(path_id: str) -> dict:
    pkg = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala" / "lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(p for p in pkg["correlation_paths"] if p["id"] == path_id)


def simulate_issue_row(*, select_route: str, do_route: str = "skip") -> dict:
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
    routes = {
        "select_next_issue": select_route,
        "select_issue_do": do_route,
        "select_issue_executor": do_route,
    }
    status: dict[str, str] = {}

    def matches(when: dict) -> bool:
        if not when:
            return True
        upstream = str(when.get("upstream") or "")
        if status.get(upstream) != "succeeded":
            return False
        return routes.get(upstream) == when.get("equals")

    pending = list(_path_raw("issue_row")["effectors"])
    progressed = True
    while pending and progressed:
        progressed = False
        leftover = []
        for node in pending:
            deps = list(node.get("conduction") or [])
            if any(status.get(dep) not in {"succeeded", "skipped"} for dep in deps):
                leftover.append(node)
                continue
            name = str(node["id"])
            status[name] = "succeeded" if matches(dict(node.get("when") or {})) else "skipped"
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def _require_fala_host():
    pytest.importorskip("fala")
    os.environ.setdefault("FALA_HOME", os.environ.get("FALA_HOME") or "/Fala")
    try:
        from fala._build import ensure_process_host_library

        ensure_process_host_library()
    except Exception as exc:
        pytest.skip(f"fala host unavailable: {exc}")


def _statuses(result):
    return {name: row["status"] for name, row in result["effector_results"].items()}


def test_empty_list_still_reaches_receipt():
    status = simulate_issue_row(select_route="none", do_route="skip")
    assert status["issues_run_triage"] == "skipped"
    assert status["select_issue_do"] == "succeeded"
    assert status["issues_launch_pr"] == "skipped"
    assert status["summarize_issue_row"] == "succeeded"


def test_sito_skip_still_reaches_receipt():
    status = simulate_issue_row(select_route="issue", do_route="skip")
    assert status["issues_run_triage"] == "succeeded"
    assert status["issues_launch_pr"] == "skipped"
    assert status["summarize_issue_row"] == "succeeded"


def test_sito_do_waits_for_launch_then_receipt():
    status = simulate_issue_row(select_route="issue", do_route="do")
    assert status["issues_launch_pr"] == "succeeded"
    assert status["summarize_issue_row"] == "succeeded"


def test_issues_parent_is_list_then_nest_then_receipt(tmp_path):
    _require_fala_host()
    receipt = tmp_path / "issues-receipt.json"
    body = base_effector(
        f"""if a=='list_open_issues':v.update(issues=[],count=0,overflow=False)
if a=='run_issue_rows':v.update(route='idle',result={{'route':'none','leftover':0}})
if a=='summarize_issues':v['result']={{'route':'none'}};Path({str(receipt)!r}).write_text('receipt')"""
    )
    result = run_graph(tmp_path, body, "issues-nest", path_id="issues")
    status = _statuses(result)
    assert status["list_open_issues"] == "succeeded"
    assert status["run_issue_rows"] == "succeeded"
    assert status["summarize_issues"] == "succeeded"
    assert "select_next_issue" not in status
    assert "run_product_factory_pass_1" not in status
    assert receipt.is_file()
    assert not any(name.endswith("_8") or name.endswith("_9") for name in status)


def test_empty_list_skips_implement_and_writes_receipt(tmp_path):
    _require_fala_host()
    receipt = tmp_path / "issues-receipt.json"
    body = base_effector(
        f"""if a=='select_next_issue':v.update(route='none',reason='empty')
if a=='select_issue_do':v.update(route='skip',reason='no_issue')
if a=='select_issue_executor':v.update(route='skip',reason='no_issue')
if a=='summarize_issue_row':v['result']={{'route':'none'}};Path({str(receipt)!r}).write_text('receipt')"""
    )
    result = run_graph(tmp_path, body, "issue-row-empty", path_id="issue_row")
    status = _statuses(result)
    assert status["select_next_issue"] == "succeeded"
    assert status["issues_run_triage"] == "skipped"
    assert status["select_issue_do"] == "succeeded"
    assert status["issues_launch_pr"] == "skipped"
    assert status["summarize_issue_row"] == "succeeded"
    assert receipt.is_file()


def test_sito_skip_does_not_launch_and_writes_receipt(tmp_path):
    _require_fala_host()
    receipt = tmp_path / "issues-receipt.json"
    body = base_effector(
        f"""if a=='select_next_issue':v.update(route='issue',repo='o/r',issue=2)
if a=='issues_run_triage':v.update(route='completed',triage={{'result':{{'implementable':False}}}})
if a=='select_issue_do':v.update(route='skip',reason='sito_nie_robic')
if a=='select_issue_executor':v.update(route='skip',reason='sito_nie_robic')
if a=='issues_launch_pr':Path({str(tmp_path/'launched')!r}).write_text('launched')
if a=='summarize_issue_row':v['result']={{'route':'skip'}};Path({str(receipt)!r}).write_text('receipt')"""
    )
    result = run_graph(tmp_path, body, "issue-row-skip", path_id="issue_row")
    status = _statuses(result)
    assert status["issues_run_triage"] == "succeeded"
    assert status["select_issue_do"] == "succeeded"
    assert status["issues_launch_pr"] == "skipped"
    assert status["summarize_issue_row"] == "succeeded"
    assert receipt.is_file()
    assert not (tmp_path / "launched").exists()


def test_sito_do_launches_one_issue_to_pr_and_writes_receipt(tmp_path):
    _require_fala_host()
    receipt = tmp_path / "issues-receipt.json"
    launched = tmp_path / "launched"
    body = base_effector(
        f"""if a=='select_next_issue':v.update(route='issue',repo='o/r',issue=2,leftover=1)
if a=='issues_run_triage':v.update(route='completed',triage={{'result':{{'implementable':True}}}})
if a=='select_issue_do':v.update(route='do',repo='o/r',issue=2)
if a=='select_issue_executor':v.update(route='do',repo='o/r',issue=2)
if a=='issues_launch_pr':Path({str(launched)!r}).write_text('launched');v.update(route='started')
if a=='summarize_issue_row':v['result']={{'route':'do','launched':'started'}};Path({str(receipt)!r}).write_text('receipt')"""
    )
    result = run_graph(tmp_path, body, "issue-row-do", path_id="issue_row")
    status = _statuses(result)
    assert status["issues_launch_pr"] == "succeeded"
    assert status["summarize_issue_row"] == "succeeded"
    assert launched.is_file() and receipt.is_file()
