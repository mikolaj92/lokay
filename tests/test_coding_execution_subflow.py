"""coding_execution child: isolated journal and classified failed route."""

from pathlib import Path

from lokay.organ.coding_boundary import handle_coding_boundary
from lokay.proc.coding_execution_subflow import failed, run


FIRE_STEP = "sqlite.fire: failed to step query"


def test_failed_helper_is_succeeded_classified_route():
    out = failed(FIRE_STEP)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["result"]["route"] == "failed"
    assert FIRE_STEP in str(out["error"])


def test_nested_fire_step_exception_yields_route(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError(FIRE_STEP)

    monkeypatch.setattr("lokay.proc.coding_execution_subflow.run_path", boom)
    out = run(
        config_path=None,
        live=False,
        extra_inputs={"repo": "Temida/Temida", "issue": 4999},
    )
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert FIRE_STEP in str(out["error"])


def test_nested_fire_not_ok_yields_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.coding_execution_subflow.run_path",
        lambda **_k: {"ok": False, "error": FIRE_STEP},
    )
    out = run(
        config_path=None,
        live=False,
        extra_inputs={"repo": "Temida/Temida", "issue": 4996},
    )
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_empty_child_yields_classified_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.coding_execution_subflow.run_path",
        lambda **_k: {"ok": True, "route": "", "decision": {}},
    )
    out = run(
        config_path=None,
        live=False,
        extra_inputs={"repo": "Temida/Temida", "issue": 4997},
    )
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_fire_failure_does_not_mark_issue_to_pr_adapter_failed(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.coding_execution_subflow.run_path",
        lambda **_k: {"ok": False, "error": FIRE_STEP},
    )
    out = handle_coding_boundary(
        "coding_execution",
        {"live": False, "repo": "Temida/Temida", "issue": 4999},
        {},
        {"repo": "Temida/Temida", "issue_number": 4999},
    )
    assert out is not None
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out.get("status") != "failed"
    assert out.get("_exit", 0) == 0
    assert FIRE_STEP in str(out.get("error") or "")


def test_overlapping_coding_execution_runs_do_not_share_host_sqlite(
    monkeypatch, tmp_path
):
    from lokay import graph_run

    monkeypatch.setenv("HOME", str(tmp_path))
    captured: list[Path] = []

    def fake_host(**kwargs):
        captured.append(Path(kwargs["db_path"]))
        return {
            "ok": True,
            "run_status": "completed",
            "effector_results": {
                "coding_execution_terminal": {
                    "status": "succeeded",
                    "output": {
                        "values": {
                            "ok": True,
                            "route": "implemented",
                            "result": {"ok": True, "route": "implemented"},
                        }
                    },
                }
            },
        }

    monkeypatch.setattr("fala.host_run_package", fake_host)
    for issue in (4999, 4996):
        graph_run.run_path(
            path_id="coding_execution",
            repo="Temida/Temida",
            issue=issue,
            live=False,
            package_path=graph_run.find_default_package(),
        )
    assert len(captured) == 2
    assert captured[0] != captured[1]
    shared = tmp_path / ".lokay" / "fala" / "state.sqlite"
    assert shared not in captured
    assert "coding-execution" in str(captured[0])
    assert "4999" in str(captured[0])
    assert "4996" in str(captured[1])
