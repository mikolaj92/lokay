"""Run a Fala correlation path from lokay's package (order is the product)."""

from __future__ import annotations

import os
import re
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    """Resolve checkout root (editable src layout or CWD)."""
    here = Path(__file__).resolve()
    # src/lokay/graph_run.py → parents[2] == repo root
    src_layout = here.parents[2]
    if (src_layout / "fala" / "lokay.fala-package.toml").is_file():
        return src_layout
    cwd = Path.cwd()
    if (cwd / "fala" / "lokay.fala-package.toml").is_file():
        return cwd
    # packaged data next to this module
    data = here.parent / "data" / "lokay.fala-package.toml"
    if data.is_file():
        return here.parent  # not really project root; find_package handles
    return cwd


def find_default_package() -> Path:
    env = os.environ.get("LOKAY_FALA_PACKAGE")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "fala" / "lokay.fala-package.toml",  # src/lokay → repo
        Path.cwd() / "fala" / "lokay.fala-package.toml",
        here.parent / "data" / "lokay.fala-package.toml",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "fala/lokay.fala-package.toml not found; set LOKAY_FALA_PACKAGE or run from repo root"
    )


ROOT = _project_root()


def _materialize_package(src: Path, dest: Path, *, project: Path) -> Path:
    """Write package with absolute project path; organs always run via `uv run`.

    Canonical substitution only: PLACEHOLDER_PROJECT → checkout path.
    Package adapters hardcode `uv` (never bare python3 / PLACEHOLDER_PYTHON).
    """
    text = src.read_text(encoding="utf-8")
    text = text.replace("PLACEHOLDER_PROJECT", str(project.resolve()))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest


def run_path(
    *,
    path_id: str,
    repo: str,
    issue: int | None = None,
    pr: int | None = None,
    branch: str | None = None,
    config_path: str | Path | None = None,
    live: bool = False,
    package_path: str | Path | None = None,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    max_ticks: int = 64,
    extra_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drive Fala host_run_package for a Lokay graph path."""
    # Preserve the daemon-issued capability across any defensive nested check.
    inherited_health_lease = os.environ.get("LOKAY_HEALTH_LEASE", "")
    if live:
        from lokay.preflight import require_healthy

        require_healthy(str(config_path) if config_path else None)
    try:
        from fala import host_run_package
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "fala package is required: uv add / path to Fala python binding"
        ) from exc

    # Package effectors explicitly inherit the health capability. Fala requires
    # every declared key to exist, including read-only runs where it is empty.
    # Do not let a nested preflight replace the parent's valid process-tree
    # token; only the lock-owning daemon may issue/revoke that capability.
    os.environ.setdefault("LOKAY_HEALTH_LEASE", "")

    pkg_src = Path(package_path) if package_path else find_default_package()
    if not pkg_src.is_file():
        raise FileNotFoundError(f"Fala package not found: {pkg_src}")

    if db_path:
        work = Path(db_path)
    elif (
        path_id in {"issue_to_pr", "issue_to_pr_delivery", "issue_split"}
        and issue is not None
        and "/" in str(repo)
    ):
        owner, name = str(repo).split("/", 1)
        family = {
            "issue_to_pr": "i2pr",
            "issue_to_pr_delivery": "i2pr-delivery",
            "issue_split": "issue-split",
        }[path_id]
        work = (
            Path.home() / ".lokay" / "fala" / family / f"{owner}__{name}__{int(issue)}"
        )
    else:
        work = Path.home() / ".lokay" / "fala"
    work.mkdir(parents=True, exist_ok=True)
    pkg_runtime = work / "lokay.fala-package.toml"
    project = _project_root()
    # Prefer repo root that contains pyproject.toml for uv --project
    if not (project / "pyproject.toml").is_file():
        for cand in (Path.cwd(), pkg_src.resolve().parents[1]):
            if (cand / "pyproject.toml").is_file() and (cand / "fala").is_dir():
                project = cand
                break
    _materialize_package(pkg_src, pkg_runtime, project=project)
    db = work / "state.sqlite"

    if os.environ.get("LOKAY_HEALTH_LEASE", "") != inherited_health_lease:
        os.environ["LOKAY_HEALTH_LEASE"] = inherited_health_lease

    cfg = str(Path(config_path).expanduser().resolve()) if config_path else ""
    base_input: dict[str, Any] = {
        "repo": repo,
        "live": bool(live),
    }
    if cfg:
        base_input["config_path"] = cfg
        os.environ.setdefault("LOKAY_CONFIG", cfg)
    if issue is not None:
        base_input["issue"] = int(issue)
        base_input["issue_number"] = int(issue)
    if pr is not None:
        base_input["pr"] = int(pr)
        base_input["pr_number"] = int(pr)
    if branch:
        base_input["branch"] = str(branch)
    if path_id == "pr_repair":
        base_input["mode"] = "repair"
    if extra_inputs:
        base_input.update(extra_inputs)

    # Instantiate inputs from the authored Fala path. Python does not duplicate the
    # graph: it only supplies the same external envelope to each authored node.
    import tomllib

    package = tomllib.loads(pkg_src.read_text(encoding="utf-8"))
    path = next(
        (
            item
            for item in package.get("correlation_paths", [])
            if item.get("id") == path_id
        ),
        None,
    )
    if path is None:
        raise ValueError(f"unknown Fala correlation path: {path_id}")
    effector_inputs = {
        str(step["id"]): dict(base_input) for step in path.get("effectors", [])
    }

    rid = run_id or f"lokay-{uuid.uuid4().hex[:12]}"
    # Ensure organ imports resolve from checkout when not fully installed
    root = _project_root()
    src = root / "src"
    if src.is_dir():
        prev = os.environ.get("PYTHONPATH", "")
        if str(src) not in prev.split(os.pathsep):
            os.environ["PYTHONPATH"] = str(src) + (os.pathsep + prev if prev else "")

    # Fala inherit_env is a whitelist. Nested factory_pass host_ff requires the
    # key even when mill-daemon did not set it (standalone lokay-daemon / tests).
    os.environ.setdefault("LOKAY_HOST_FF_FETCHED", "")

    # Fala Mojo sources: FALA_HOME env, else sibling ../Fala only (no machine hardcodes).
    if not os.environ.get("FALA_HOME"):
        for candidate in (root.parent / "Fala", Path.cwd().parent / "Fala"):
            if (candidate / "mojo" / "fala").is_dir():
                os.environ["FALA_HOME"] = str(candidate.resolve())
                break

    previous_issue_guard = os.environ.get("LOKAY_DISABLE_HEALTH_LEASE_ISSUE")
    if inherited_health_lease:
        os.environ["LOKAY_DISABLE_HEALTH_LEASE_ISSUE"] = "1"
    try:
        # The host persists its detailed journal in ``db``; its stdout copy can
        # be hundreds of kilobytes and must not leak into the daemon log.
        with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink):
            result = host_run_package(
                db_path=db,
                package_path=pkg_runtime,
                path_id=path_id,
                run_id=rid,
                effector_inputs=effector_inputs,
                max_ticks=max_ticks,
                worker_id="lokay-graph",
            )
    finally:
        if previous_issue_guard is None:
            os.environ.pop("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", None)
        else:
            os.environ["LOKAY_DISABLE_HEALTH_LEASE_ISSUE"] = previous_issue_guard
    envelope = {
        "ok": (
            bool(result.get("ok"))
            and str(result.get("run_status") or "completed") == "completed"
        ),
        "engine": "fala",
        "path_id": path_id,
        "package": str(pkg_runtime),
        "db": str(db),
        "run_id": rid,
        "repo": repo,
        "issue": issue,
        "pr": pr,
        "branch": branch,
        "live": live,
        "fala": result,
    }
    return normalize_path_result(envelope)


def _process_payload(process: dict[str, Any]) -> dict[str, Any]:
    """Unwrap one terminal Fala effector output into the atom envelope."""
    raw = process.get("output")
    if raw is None:
        raw = process.get("output_json")
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    values = raw.get("values")
    return dict(values if isinstance(values, dict) else raw)


_FAILED_REASON_RE = re.compile(r'"reason":\s*"([A-Za-z0-9_.:-]+)"')


def _failure_reason(item: dict[str, Any]) -> str | None:
    """Machine reason for a failed atom, when the organ supplied one.

    The organ raises failed atom values as a JSON string (truncated), so the
    reason may live inside the error text rather than in structured values.
    """
    reason = item.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    error = item.get("error")
    if isinstance(error, str) and error.startswith("{"):
        match = _FAILED_REASON_RE.search(error[:2000])
        if match:
            return match.group(1)
    return None


def normalize_path_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize Fala's ``id/status/output/error`` process entries.

    Compose callers never interpret host internals.  A failed host/process stays
    failed, while successful terminal atom values form the existing contracts.
    """
    fala = result.get("fala") if isinstance(result.get("fala"), dict) else {}
    effector_results = fala.get("effector_results")
    entries: list[tuple[str, dict[str, Any]]] = []
    results_error: str | None = None
    if effector_results is not None:
        if not isinstance(effector_results, dict) or not effector_results:
            results_error = "Fala effector_results is missing or malformed"
        elif any(not isinstance(value, dict) for value in effector_results.values()):
            results_error = "Fala effector_results contains a malformed entry"
        else:
            entries = [(str(key), value) for key, value in effector_results.items()]
            for _key, value in entries:
                status = str(value.get("status") or "").lower()
                if status in {"completed", "succeeded", "success"}:
                    raw_output = value.get("output")
                    if raw_output is None:
                        raw_output = value.get("output_json")
                    if isinstance(raw_output, str):
                        import json

                        try:
                            raw_output = json.loads(raw_output)
                        except (TypeError, ValueError):
                            raw_output = None
                    if not isinstance(raw_output, dict):
                        results_error = (
                            "Fala effector_results contains a completed entry "
                            "without structured output"
                        )
                        entries = []
                        break
    else:
        # Compatibility with hosts that embedded terminal output in processes.
        # Fala's id/status-only process summaries are deliberately not accepted.
        processes = fala.get("processes")
        if isinstance(processes, list):
            legacy = [
                value
                for value in processes
                if isinstance(value, dict)
                and ("output" in value or "output_json" in value)
            ]
            entries = [
                (
                    str(
                        value.get("effector_id")
                        or str(value.get("id") or "").rsplit(":", 1)[-1]
                    ),
                    value,
                )
                for value in legacy
            ]
        if not entries:
            results_error = "Fala completed without terminal effector_results"

    terminal: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for keyed_id, process in entries:
        process_id = str(process.get("id") or "")
        effector_id = keyed_id or str(
            process.get("effector_id") or process_id.rsplit(":", 1)[-1]
        )
        payload = _process_payload(process)
        item = {"step": effector_id, "status": process.get("status"), **payload}
        error = process.get("error")
        if error not in (None, "", {}):
            item["error"] = error
        terminal[effector_id] = item
        steps.append(item)
        status = str(process.get("status") or "").lower()
        if status in {"failed", "cancelled", "canceled", "timed_out", "error"}:
            failed.append(item)

    out = {**result, "terminal": terminal, "steps": steps}
    if results_error and result.get("ok"):
        out.update(ok=False, error=results_error)
        return out
    if failed or not result.get("ok"):
        out["ok"] = False
        out["error"] = failed[0].get("error") if failed else result.get("error")
        if not out.get("error"):
            out["error"] = "Fala path failed"
        if failed:
            reason = _failure_reason(failed[0])
            if reason:
                out["reason"] = reason
        if (
            str(result.get("path_id") or "") == "factory_pass"
            and out.get("reason") == "host_updated"
        ):
            out["health"] = "host_updated"
            out["restart_required"] = True
        return out

    out["ok"] = True
    authored_results = [
        item.get("result")
        for item in terminal.values()
        if isinstance(item.get("result"), dict)
    ]
    if authored_results:
        out.update(authored_results[-1])
        return out
    path_id = str(result.get("path_id") or "")
    if path_id == "self_repair":
        fresh = terminal.get("self_repair_preflight", {})
        pushed = terminal.get("self_repair_push_main", {})
        activate = terminal.get("self_repair_activate", {})
        closed = terminal.get("self_repair_close", {})
        commit = str(
            fresh.get("commit") or pushed.get("commit") or activate.get("commit") or ""
        )
        validated = fresh.get("validated") is True
        restart_required = fresh.get("restart_required") is True
        published_dirty = (
            activate.get("published") is True
            and str(activate.get("reason") or "") == "dirty_tree"
        )
        gate_released = bool(validated and restart_required)
        out.update(
            validated=validated or published_dirty,
            restart_required=restart_required or published_dirty,
            commit=commit or None,
            incident_closed=closed.get("closed") is True,
            gate_released=gate_released,
        )
        if published_dirty and not gate_released:
            out.update(ok=True, reason="published_push_kept_dirty_tree")
        elif not out["validated"] or not out["restart_required"]:
            out.update(ok=False, error="self-repair did not validate activated main")
    elif path_id == "daemon_cycle":
        mill = terminal.get("recovery_mill", {}).get("mill")
        if not isinstance(mill, dict):
            out.update(ok=False, error="daemon cycle completed without mill envelope")
        else:
            repair = terminal.get("recovery_run_self_repair", {})
            if repair.get("restart_required") is True:
                out.update(
                    ok=False,
                    health="self_repair_restart_required",
                    error="confirmed stall repaired; restart required before product work",
                    self_repair=repair,
                )
            else:
                out.update(mill)
    elif path_id == "factory_pass":
        # Terminal receipt atom carries the full tick envelope. Fall back to
        # legacy factory_tick wrapper if an old journal/result is normalized.
        recorded = terminal.get("record_pass", {})
        factory = terminal.get("factory_tick", {})
        tick = recorded.get("tick") if isinstance(recorded.get("tick"), dict) else None
        if tick is None:
            tick = (
                factory.get("tick")
                if isinstance(factory.get("tick"), dict)
                else factory
            )
        if not isinstance(tick, dict):
            tick = {}
        out.update(
            {
                key: value
                for key, value in tick.items()
                if key not in {"step", "status", "atom", "_exit"}
            }
        )
        out["ok"] = bool(tick.get("ok", True))
        if not out["ok"]:
            out["error"] = tick.get("error") or "factory pass failed"
    return out


def describe_package(package_path: str | Path | None = None) -> dict[str, Any]:
    """Parse graph structure without running (order inspection)."""
    import tomllib

    pkg = Path(package_path) if package_path else find_default_package()
    data = tomllib.loads(pkg.read_text(encoding="utf-8"))
    paths = []
    for path in data.get("correlation_paths") or []:
        effectors = path.get("effectors") or []
        nodes = []
        for eff in effectors:
            nodes.append(
                {
                    "id": eff.get("id"),
                    "atom": (eff.get("config") or {}).get("atom"),
                    "conduction": list(eff.get("conduction") or []),
                    "when": dict(eff.get("when") or {}),
                }
            )
        paths.append({"id": path.get("id"), "title": path.get("title"), "nodes": nodes})
    return {"package_id": data.get("id"), "paths": paths}
