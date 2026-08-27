"""prs NODE: four authored nodes. Child pr_triage is a named slot."""

import tomllib
from pathlib import Path

from test_factory_pass_fala import _require_fala_host
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


PRS_ATOMS = (
    "list_open_prs",
    "select_next_pr",
    "run_pr_triage_subflow",
    "summarize_prs",
)


def _prs_path() -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == "prs")


def simulate_prs(*, select_route: str) -> dict[str, str]:
    routes = {"select_next_pr": select_route}
    status: dict[str, str] = {}
    pending = list(_prs_path()["effectors"])
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
                if status.get(upstream) != "succeeded" or routes.get(upstream) != when.get(
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


def test_empty_list_skips_child_slot():
    status = simulate_prs(select_route="none")
    assert status["list_open_prs"] == "succeeded"
    assert status["select_next_pr"] == "succeeded"
    assert status["run_pr_triage_subflow"] == "skipped"
    assert status["summarize_prs"] == "succeeded"


def test_empty_list_skips_triage_and_finishes(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='list_open_prs':v.update(prs=[],count=0)
if a=='select_next_pr':v.update(route='none',reason='no_open_pr')
if a=='summarize_prs':v['result']={'route':'none'}"""
    )
    result = run_graph(tmp_path, body, "prs-empty", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["run_pr_triage_subflow"] == "skipped"
    assert status["summarize_prs"] == "succeeded"


def test_one_pr_launches_child_slot():
    status = simulate_prs(select_route="pr")
    assert status["run_pr_triage_subflow"] == "succeeded"
    assert status["summarize_prs"] == "succeeded"


def test_one_pr_runs_triage(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='list_open_prs':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='select_next_pr':v.update(route='pr',repo='o/r',pr=9,branch='ai/fix/9-x')
if a=='run_pr_triage_subflow':v.update(route='completed')
if a=='summarize_prs':v['result']={'route':'pr','triaged':'completed'}"""
    )
    result = run_graph(tmp_path, body, "prs-one", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert list(status) == list(PRS_ATOMS)


def test_prs_atoms_are_the_four_named_nodes():
    ids = [str(node["id"]) for node in _prs_path()["effectors"]]
    assert ids == list(PRS_ATOMS)
    assert len(ids) == len(set(ids))
    others = [
        str(node["id"])
        for row in tomllib.loads(
            (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
                encoding="utf-8"
            )
        )["correlation_paths"]
        if row["id"] != "prs"
        for node in row.get("effectors") or []
    ]
    assert not set(ids).intersection(others)


def test_prs_readme_names_the_child_slot():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    assert "RunPrTriageSubflow" in readme
    assert "run_pr_triage_subflow" in graph
    assert "pr_triage" in graph
    assert "Named child slot" in graph
    assert "run_pr_triage_subflow" in graph
