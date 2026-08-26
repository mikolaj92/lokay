"""Daemon cycle: repair is a side child; factory always runs."""

import tomllib
from pathlib import Path

from lokay.graph_run import find_default_package


def _daemon_cycle_raw() -> dict:
    pkg = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    return next(p for p in pkg["correlation_paths"] if p["id"] == "daemon_cycle")


def simulate_daemon_cycle(*, classify_route: str) -> dict[str, str]:
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
    status: dict[str, str] = {}

    def matches(when: dict) -> bool:
        if not when:
            return True
        upstream = str(when.get("upstream") or "")
        if status.get(upstream) != "succeeded":
            return False
        return classify_route == when.get("equals")

    pending = list(_daemon_cycle_raw()["effectors"])
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
            status[name] = (
                "succeeded" if matches(dict(node.get("when") or {})) else "skipped"
            )
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def test_daemon_cycle_starts_with_last_pass_gate_not_recovery_begin():
    ids = [node["id"] for node in _daemon_cycle_raw()["effectors"]]
    assert ids[0] == "classify_last_pass_progress"
    assert "recovery_begin" not in ids
    assert "recovery_observe" not in ids
    assert "recovery_record" not in ids
    assert ids[-2] == "recovery_mill"
    assert ids[-1] == "summarize_daemon_cycle"


def test_leftover_skip_runs_factory_and_skips_repair():
    status = simulate_daemon_cycle(classify_route="factory")
    assert status["classify_last_pass_progress"] == "succeeded"
    assert status["recovery_incident"] == "skipped"
    assert status["recovery_run_self_repair"] == "skipped"
    assert status["recovery_mill"] == "succeeded"
    assert status["summarize_daemon_cycle"] == "succeeded"


def test_did_not_move_runs_repair_then_factory():
    status = simulate_daemon_cycle(classify_route="repair")
    assert status["classify_last_pass_progress"] == "succeeded"
    assert status["recovery_incident"] == "succeeded"
    assert status["recovery_run_self_repair"] == "succeeded"
    assert status["recovery_mill"] == "succeeded"
    assert status["summarize_daemon_cycle"] == "succeeded"


def test_docs_say_repair_returns_to_factory():
    graph = (Path(__file__).resolve().parents[1] / "docs" / "GRAPH.md").read_text(
        encoding="utf-8"
    )
    section = graph.split("### `daemon_cycle`")[1].split("### `factory_pass`")[0]
    assert "classify_last_pass_progress" in section
    assert "leftover skip" in section.lower() or "leftover_overflow" in section
    assert "recovery_mill" in section
    assert "recovery_begin" not in section.split("```")[1]
