"""Native Fala proofs for the prs child: empty skip, one PR, unique names."""

import tomllib
from pathlib import Path

from test_factory_pass_fala import _require_fala_host
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


PRS_ATOMS = (
    "read_prs_scope",
    "list_open_prs",
    "filter_mill_prs",
    "select_next_pr",
    "prs_run_triage",
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
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
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


def test_empty_list_skips_triage_and_does_not_fail():
    status = simulate_prs(select_route="none")
    for name in (
        "read_prs_scope",
        "list_open_prs",
        "filter_mill_prs",
        "select_next_pr",
        "summarize_prs",
    ):
        assert status[name] == "succeeded", name
    assert status["prs_run_triage"] == "skipped"


def test_empty_list_skips_triage_and_finishes(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='read_prs_scope':v.update(repos=[],prefix='ai/fix/')
if a=='list_open_prs':v.update(prs=[],count=0)
if a=='filter_mill_prs':v.update(prs=[],count=0)
if a=='select_next_pr':v.update(route='none',reason='no_open_pr')
if a=='summarize_prs':v['result']={'route':'none'}"""
    )
    result = run_graph(tmp_path, body, "prs-empty", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["filter_mill_prs"] == "succeeded"
    assert status["prs_run_triage"] == "skipped"
    assert status["summarize_prs"] == "succeeded"
    assert result.get("ok") is not False


def test_one_pr_conduction_runs_triage():
    status = simulate_prs(select_route="pr")
    assert status["prs_run_triage"] == "succeeded"
    assert status["summarize_prs"] == "succeeded"


def test_one_pr_runs_triage(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='read_prs_scope':v.update(repos=['o/r'],prefix='ai/fix/')
if a=='list_open_prs':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='filter_mill_prs':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='select_next_pr':v.update(route='pr',repo='o/r',pr=9,branch='ai/fix/9-x')
if a=='prs_run_triage':v.update(route='completed')
if a=='summarize_prs':v['result']={'route':'pr','triaged':'completed'}"""
    )
    result = run_graph(tmp_path, body, "prs-one", path_id="prs")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["prs_run_triage"] == "succeeded"
    assert status["summarize_prs"] == "succeeded"
    assert list(status) == list(PRS_ATOMS)


def test_prs_atoms_are_unique_and_not_a_slot_catalog():
    path = _prs_path()
    ids = [str(node["id"]) for node in path["effectors"]]
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
    assert not any("slot" in name or "catalog" in name for name in ids)


def test_prs_path_is_in_readme_and_not_leftover_overflow():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    assert "### Recenzja i merge PR-ów — `prs`" in readme
    assert "ReadPrsScope" in readme
    assert "FilterMillPrs" in readme
    assert "PrsRunTriage" in readme
    assert "### `prs`" in graph
    assert "read_prs_scope" in graph
    assert "filter_mill_prs" in graph
    assert "leftover overflow" in graph.lower()
    assert "compose_pr_triage" in graph
