"""Audit expanded Fala graph nodes and their independent suite metadata."""
from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


def _literal(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise ValueError(f"{path}: missing literal {name}")


def _walk_effectors(package: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for path in package.get("correlation_paths", []):
        path_id = str(path.get("id"))
        for key in ("effectors", "prefix_effectors", "suffix_effectors"):
            for node in path.get(key, []) or []:
                rows.append((f"{path_id}.{key}.{node.get('id')}", node))
    for template in package.get("path_templates", []) or []:
        template_id = str(template.get("id"))
        for node in template.get("effectors", []) or []:
            rows.append((f"template.{template_id}.{node.get('id')}", node))
    return rows


def audit(root: Path) -> dict[str, Any]:
    package = tomllib.loads((root / "fala/lokay.fala-package.toml").read_text(encoding="utf-8"))
    expanded = json.loads((root / "fala/lokay.expanded.golden.json").read_text(encoding="utf-8"))
    paths = {str(path["id"]): path for path in expanded["correlation_paths"]}
    missing: list[dict[str, str]] = []
    extra: list[dict[str, str]] = []
    metadata: list[dict[str, Any]] = []
    for path_id, path in paths.items():
        expected = {str(node["id"]): node for node in path.get("effectors", [])}
        directory = root / "tests/graphs" / path_id
        actual = {
            p.stem.removeprefix("test_")
            for p in directory.glob("test_*.py")
            if p.name not in {"test_graph.py", "test_transitions.py"}
        }
        for node_id in sorted(set(expected) - actual):
            missing.append({"path": path_id, "node": node_id})
        for node_id in sorted(actual - set(expected)):
            extra.append({"path": path_id, "node": node_id})
        mismatches: list[dict[str, Any]] = []
        for node_id in sorted(set(expected) & actual):
            node_file = directory / f"test_{node_id}.py"
            got_cond = _literal(node_file, "_CONDUCTION")
            got_when = _literal(node_file, "_WHEN")
            want = expected[node_id]
            if got_cond != want.get("conduction", []):
                mismatches.append({"node": node_id, "field": "conduction"})
            if got_when != want.get("when"):
                mismatches.append({"node": node_id, "field": "when"})
        expected_edges = {
            (str(upstream), node_id)
            for node_id, node in expected.items()
            for upstream in node.get("conduction", [])
        }
        got_edges = set(tuple(edge) for edge in _literal(directory / "test_transitions.py", "_COND_EDGES"))
        expected_when = {
            (node_id, json.dumps(node["when"], sort_keys=True, separators=(",", ":")))
            for node_id, node in expected.items()
            if node.get("when")
        }
        got_when = {
            (str(node_id), json.dumps(when, sort_keys=True, separators=(",", ":")))
            for node_id, when in _literal(directory / "test_transitions.py", "_WHEN_BRANCHES")
        }
        if expected_edges != got_edges:
            mismatches.append({"field": "_COND_EDGES"})
        if expected_when != got_when:
            mismatches.append({"field": "_WHEN_BRANCHES"})
        graph_file = directory / "test_graph.py"
        graph_text = graph_file.read_text(encoding="utf-8")
        if "host_drive" in graph_text:
            mismatches.append({"field": "host_drive"})
        if "run_overridden_path" not in graph_text:
            mismatches.append({"field": "native_host_run_package"})
        metadata.append(
            {
                "path": path_id,
                "nodes": len(expected),
                "node_suites": len(actual),
                "conduction_edges": len(expected_edges),
                "when_branches": len(expected_when),
                "mismatches": mismatches,
            }
        )
    authored_nodes = _walk_effectors(package)
    missing_schema = [name for name, node in authored_nodes if not node.get("output_schema")]
    totals = {
        "paths": len(paths),
        "expanded_nodes": sum(len(path.get("effectors", [])) for path in paths.values()),
        "node_suites": sum(row["node_suites"] for row in metadata),
        "conduction_edges": sum(
            len(node.get("conduction", []))
            for path in paths.values()
            for node in path.get("effectors", [])
        ),
        "when_branches": sum(
            bool(node.get("when"))
            for path in paths.values()
            for node in path.get("effectors", [])
        ),
        "authored_nodes": sum(len(path.get("effectors", [])) for path in package.get("correlation_paths", [])),
        "authored_effectors_with_schema": len(authored_nodes) - len(missing_schema),
        "authored_effectors_missing_schema": len(missing_schema),
    }
    return {
        "authority": "fala/lokay.expanded.golden.json",
        "totals": totals,
        "paths": metadata,
        "missing_node_suites": missing,
        "extra_node_suites": extra,
        "missing_output_schema": missing_schema,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    report = audit(args.root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    failed = (
        report["missing_node_suites"]
        or report["extra_node_suites"]
        or report["missing_output_schema"]
        or any(row["mismatches"] for row in report["paths"])
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
