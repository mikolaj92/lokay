"""Native Fala proofs: parent conducts four children, not leaves."""

import pytest

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector

CHILDREN = (
    "factory_begin",
    "closeout_prs",
    "reap_stale_worktrees",
    "dispatch_implement",
    "record_pass",
    "factory_pass_terminal",
)

LEAVES = (
    "host_ff",
    "factory_begin_host_gate",
    "select_implement",
    "queue_conflict",
    "survey_prs",
    "classify_factory_idle",
)


def _body(receipt_mark: str) -> str:
    kids = " ".join(repr(name) for name in CHILDREN)
    return base_effector(
        f"""if a=='factory_begin':v.update(pass_dir='/pass')
if a=='record_pass':Path({receipt_mark!r}).write_text('receipt');v.update(result={{'ok':True,'health':'progress'}})
if a=='factory_pass_terminal':v.update(result={{'ok':True,'health':'progress'}})
if a in {{{kids}}}:v.update(ok=True)"""
    )


def _require_fala_host():
    pytest.importorskip("fala")
    try:
        from fala._build import ensure_process_host_library

        ensure_process_host_library()
    except Exception as exc:
        pytest.skip(f"fala host unavailable: {exc}")


def test_parent_runs_only_child_subgraphs(tmp_path):
    _require_fala_host()
    receipt = str(tmp_path / "receipt")
    result = run_graph(
        tmp_path,
        _body(receipt),
        "factory-children",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    for name in CHILDREN:
        assert status[name] == "succeeded", name
    for name in LEAVES:
        assert name not in status, name
    assert tmp_path.joinpath("receipt").is_file()
