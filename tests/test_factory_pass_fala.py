"""Native Fala proofs: one pass is PRs, clean, then at most one implement."""

import pytest

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector

ALWAYS = (
    "host_ff",
    "factory_begin_host_gate",
    "factory_begin",
    "closeout_prs",
    "reap_stale_worktrees",
    "select_implement",
    "record_pass",
    "factory_pass_terminal",
)

WORK = ("queue_conflict", "dispatch_implement")


def _body(route: str, work_mark: str, receipt_mark: str) -> str:
    always_py = " ".join(repr(name) for name in ALWAYS)
    return base_effector(
        f"""if a=='select_implement':v.update(route={route!r})
if a=='dispatch_implement':Path({work_mark!r}).write_text('dispatch')
if a=='record_pass':Path({receipt_mark!r}).write_text('receipt');v.update(result={{'ok':True,'health':'progress'}})
if a=='factory_pass_terminal':v.update(result={{'ok':True,'health':'progress'}})
if a in {{{always_py}}}:v.update(ok=True)"""
    )


def _require_fala_host():
    pytest.importorskip("fala")
    try:
        from fala._build import ensure_process_host_library

        ensure_process_host_library()
    except Exception as exc:
        pytest.skip(f"fala host unavailable: {exc}")


def test_selected_runs_prs_clean_and_implement(tmp_path):
    _require_fala_host()
    work = str(tmp_path / "dispatch")
    receipt = str(tmp_path / "receipt")
    result = run_graph(
        tmp_path,
        _body("selected", work, receipt),
        "factory-selected",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    for name in ALWAYS:
        assert status[name] == "succeeded", name
    for name in WORK:
        assert status[name] == "succeeded", name
    assert tmp_path.joinpath("dispatch").is_file()
    assert tmp_path.joinpath("receipt").is_file()
    assert "survey_prs" not in status
    assert "classify_factory_idle" not in status


def test_none_runs_prs_clean_skips_implement(tmp_path):
    _require_fala_host()
    work = str(tmp_path / "dispatch")
    receipt = str(tmp_path / "receipt")
    result = run_graph(
        tmp_path,
        _body("none", work, receipt),
        "factory-none",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    for name in ALWAYS:
        assert status[name] == "succeeded", name
    for name in WORK:
        assert status[name] == "skipped", name
    assert tmp_path.joinpath("receipt").is_file()
    assert not tmp_path.joinpath("dispatch").exists()
    assert "survey_prs" not in status
