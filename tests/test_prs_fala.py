"""Native Fala proofs for the prs child: empty skip, one PR, unique names."""

import tomllib
from pathlib import Path

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_empty_list_skips_triage_and_finishes(tmp_path):
    body = base_effector(
        """if a=='list_open_prs':v.update(prs=[],count=0)
if a=='select_next_pr':v.update(route='none',reason='no_open_pr')
if a=='summarize_prs':v['result']={'route':'none'}"""
    )
    result = run_graph(tmp_path, body, "prs-empty", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["list_open_prs"] == "succeeded"
    assert status["select_next_pr"] == "succeeded"
    assert status["prs_run_triage"] == "skipped"
    assert status["summarize_prs"] == "succeeded"
    assert result.get("ok") is not False


def test_one_pr_runs_triage(tmp_path):
    body = base_effector(
        """if a=='list_open_prs':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='select_next_pr':v.update(route='pr',repo='o/r',pr=9,branch='ai/fix/9-x')
if a=='prs_run_triage':v.update(route='completed')
if a=='summarize_prs':v['result']={'route':'pr','triaged':'completed'}"""
    )
    result = run_graph(tmp_path, body, "prs-one", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["prs_run_triage"] == "succeeded"
    assert status["summarize_prs"] == "succeeded"
    assert list(status) == [
        "list_open_prs",
        "select_next_pr",
        "prs_run_triage",
        "summarize_prs",
    ]


def test_prs_atoms_are_unique_and_not_a_slot_catalog():
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    path = next(row for row in package["correlation_paths"] if row["id"] == "prs")
    ids = [str(node["id"]) for node in path["effectors"]]
    assert ids == [
        "list_open_prs",
        "select_next_pr",
        "prs_run_triage",
        "summarize_prs",
    ]
    assert len(ids) == len(set(ids))
    others = [
        str(node["id"])
        for row in package["correlation_paths"]
        if row["id"] != "prs"
        for node in row.get("effectors") or []
    ]
    assert not set(ids).intersection(others)
    assert not any("slot" in name or "catalog" in name for name in ids)


def test_prs_path_is_in_readme_and_not_leftover_overflow():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    assert "### Recenzja i merge PR-ów — `prs`" in readme
    assert "ListOpenPrs" in readme
    assert "PrsRunTriage" in readme
    assert "### `prs`" in graph
    assert "leftover overflow" in graph.lower()
    assert "closeout_prs" in graph
