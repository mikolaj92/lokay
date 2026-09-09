"""Executable reference model for Fala conduction and conditional edges."""
from __future__ import annotations

from typing import Any


def lookup_path(values: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Read a scalar from a domain object, including dotted Fala when paths."""
    if path in values:
        return True, values[path]
    current: Any = values
    for part in str(path).split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def run_model(
    effectors: list[dict[str, Any]],
    outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Run the authored geometry and return {node_id: 'succeeded'|'skipped'}."""
    outputs = {str(k): dict(v) for k, v in (outputs or {}).items()}
    status: dict[str, str] = {}
    pending = list(effectors)
    while pending:
        progressed = False
        rest: list[dict[str, Any]] = []
        for node in pending:
            name = str(node["id"])
            deps = [str(x) for x in node.get("conduction", [])]
            if any(dep not in status for dep in deps):
                rest.append(node)
                continue
            when = node.get("when") or {}
            if when:
                upstream = str(when.get("upstream") or "")
                found, actual = lookup_path(outputs.get(upstream, {}), str(when.get("path") or ""))
                ok = status.get(upstream) == "succeeded" and found and actual == when.get("equals")
                if not ok:
                    status[name] = "skipped"
                    progressed = True
                    continue
            status[name] = "succeeded"
            progressed = True
        if not progressed:
            raise AssertionError(f"unresolved: {[str(n['id']) for n in rest]}")
        pending = rest
    return status


def node_status_map(result: dict[str, Any], path_id: str = "") -> dict[str, str]:
    """Extract {short_id: status} from host_drive or host_run_package."""
    out: dict[str, str] = {}
    results = result.get("effector_results")
    if isinstance(results, dict) and results:
        for key, row in results.items():
            if isinstance(row, dict):
                out[str(key)] = str(row.get("status", ""))
        return out
    for row in result.get("processes", []):
        full_id = str(row.get("id", ""))
        parts = full_id.split(":", 2)
        short = parts[2] if len(parts) == 3 else full_id
        if path_id and short.startswith(path_id + ":"):
            short = short[len(path_id) + 1 :]
        out[short] = str(row.get("status", ""))
    return out
