"""pr_triage department: sieve and verdict. Repair is a parent department."""

import tomllib
from pathlib import Path

from test_factory_pass_fala import _require_fala_host
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


PR_TRIAGE_ATOMS = (
    "list_pr_sieve",
    "select_pr_sieve",
    "run_pr_sieve",
    "select_pr_triage_verdict",
    "summarize_pr_triage_department",
)


def _path() -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == "pr_triage_department")


def simulate(*, select_route: str) -> dict[str, str]:
    routes = {"select_pr_sieve": select_route}
    status: dict[str, str] = {}
    pending = list(_path()["effectors"])
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


def test_package_has_no_glued_pr_product() -> None:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    ids = {str(row["id"]) for row in package["correlation_paths"]}
    assert "prs" not in ids
    assert "pr_triage_department" in ids
    assert "pr_repair" in ids


def test_empty_list_skips_sieve_child():
    status = simulate(select_route="none")
    assert status["list_pr_sieve"] == "succeeded"
    assert status["select_pr_sieve"] == "succeeded"
    assert status["run_pr_sieve"] == "skipped"
    assert status["select_pr_triage_verdict"] == "succeeded"
    assert status["summarize_pr_triage_department"] == "succeeded"


def test_empty_list_skips_triage_and_finishes(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='list_pr_sieve':v.update(prs=[],count=0)
if a=='select_pr_sieve':v.update(route='none',reason='no_open_pr')
if a=='select_pr_triage_verdict':v.update(verdict='none')
if a=='summarize_pr_triage_department':v.update(department='pr_triage',repair_started=False)"""
    )
    result = run_graph(tmp_path, body, "pr-triage-empty", path_id="pr_triage_department")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["run_pr_sieve"] == "skipped"
    assert status["summarize_pr_triage_department"] == "succeeded"


def test_one_pr_runs_sieve_without_starting_repair():
    status = simulate(select_route="pr")
    assert status["run_pr_sieve"] == "succeeded"
    assert "run_pr_repair_subflow" not in status
    assert status["summarize_pr_triage_department"] == "succeeded"


def test_one_pr_runs_triage(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='list_pr_sieve':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='select_pr_sieve':v.update(route='pr',repo='o/r',pr=9,branch='ai/fix/9-x')
if a=='run_pr_sieve':v.update(route='completed',triage={'repairable':False})
if a=='select_pr_triage_verdict':v.update(verdict='feedback')
if a=='summarize_pr_triage_department':v.update(department='pr_triage',verdict='feedback',repair_started=False)"""
    )
    result = run_graph(tmp_path, body, "pr-triage-one", path_id="pr_triage_department")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert set(status) == set(PR_TRIAGE_ATOMS)
    assert status["run_pr_sieve"] == "succeeded"
    assert "run_pr_repair_subflow" not in status


def test_repair_verdict_does_not_start_repair_inside_sieve(tmp_path):
    _require_fala_host()
    sentinel = tmp_path / "repair-ran"
    body = base_effector(
        """if a=='list_pr_sieve':v.update(prs=[{'repo':'o/r','pr':9,'branch':'ai/fix/9-x'}],count=1)
if a=='select_pr_sieve':v.update(route='pr',repo='o/r',pr=9,branch='ai/fix/9-x')
if a=='run_pr_sieve':v.update(route='completed',triage={'repairable':True})
if a=='select_pr_triage_verdict':v.update(verdict='repair',repairable=True)
if a=='run_pr_repair_subflow':Path(""" + repr(str(sentinel)) + """).write_text('ran')
if a=='summarize_pr_triage_department':v.update(department='pr_triage',verdict='repair',repair_started=False)"""
    )
    result = run_graph(tmp_path, body, "pr-triage-verdict", path_id="pr_triage_department")
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["run_pr_sieve"] == "succeeded"
    assert status["select_pr_triage_verdict"] == "succeeded"
    assert "run_pr_repair_subflow" not in status
    assert not sentinel.exists()


def test_pr_triage_atoms_are_the_five_named_nodes():
    ids = [str(node["id"]) for node in _path()["effectors"]]
    assert ids == list(PR_TRIAGE_ATOMS)
    assert len(ids) == len(set(ids))


def test_readme_names_the_department_sieve():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    assert "ListPrSieve" in readme
    assert "RunPrSieve" in readme
    assert "SelectPrTriageVerdict" in readme
    assert "run_pr_sieve" in graph
    assert "pr_triage_department" in graph
    assert "### `prs`" not in graph
