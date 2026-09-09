"""Fail closed if graph suites drift from the expanded Fala catalog."""
from __future__ import annotations

from pathlib import Path

from support.audit_node_suites import audit


def test_expanded_graph_suites_match_catalog():
    root = Path(__file__).resolve().parents[2]
    report = audit(root)
    assert report["missing_node_suites"] == []
    assert report["extra_node_suites"] == []
    assert report["missing_output_schema"] == []
    assert all(not row["mismatches"] for row in report["paths"])
    assert report["totals"]["expanded_nodes"] == report["totals"]["node_suites"]
    assert report["totals"]["authored_effectors_missing_schema"] == 0
