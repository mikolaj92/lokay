"""Authored conduction must carry review findings into repair receipts."""

from pathlib import Path
import tomllib

import pytest

from lokay.organ.pr_outcome import handle_pr_outcome


@pytest.mark.parametrize("atom", ["pr_repair_verdict", "summarize_pr_triage"])
def test_authored_review_handoff_retains_blockers(atom):
    root = Path(__file__).resolve().parents[1]
    package = tomllib.loads((root / "fala/lokay.fala-package.toml").read_text())
    graph = next(p for p in package["correlation_paths"] if p["id"] == "pr_triage")
    node = next(n for n in graph["effectors"] if n["id"] == atom)
    decision = {"verdict": "request_changes", "blocking": ["Root mount hides health endpoint"]}
    available = {
        "publish_pr_review": {"ok": True, "decision": decision},
        "select_pr_triage_outcome": {"route": "repair"},
    }
    upstream = {key: available.get(key, {}) for key in node["conduction"]}
    result = handle_pr_outcome(atom, {}, upstream, {})
    assert result is not None
    receipt = result.get("result", result)
    assert receipt["review"] == decision
