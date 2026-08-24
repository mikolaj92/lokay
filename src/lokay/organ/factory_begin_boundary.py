"""Fala bindings for authored factory-pass workspace opening."""

from typing import Any


def handle_factory_begin(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config_path = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    lease = up.get("inspect_factory_lease") or {}
    config = up.get("load_factory_config") or {}
    scope = up.get("select_factory_scope") or {}
    ledger = up.get("persist_factory_stuck") or up.get("read_factory_stuck") or {}
    workspace = up.get("create_factory_pass_dir") or {}
    built = up.get("build_factory_begin_state") or {}
    working = up.get("build_factory_working_state") or {}
    if atom == "inspect_factory_lease":
        from lokay.proc.inspect_factory_lease import inspect

        return inspect(live=live)
    if atom == "restore_factory_lease":
        from lokay.proc.restore_factory_lease import restore

        return restore(lease)
    if atom == "reinspect_factory_lease":
        from lokay.proc.reinspect_factory_lease import inspect

        return inspect(up.get("restore_factory_lease") or {})
    if atom == "run_factory_preflight":
        from lokay.proc.run_factory_preflight import run

        return run(config_path=config_path, live=live)
    if atom == "select_factory_load_route":
        routes = [
            lease,
            up.get("reinspect_factory_lease") or {},
            up.get("run_factory_preflight") or {},
        ]
        return {
            "ok": True,
            "route": (
                "load" if any(x.get("route") == "load" for x in routes) else "terminal"
            ),
        }
    if atom == "load_factory_config":
        from lokay.proc.load_factory_config import load

        return load(config_path=config_path, live=live)
    if atom == "classify_factory_mode":
        from lokay.proc.classify_factory_mode import classify

        return classify(config)
    if atom == "select_factory_scope":
        from lokay.proc.select_factory_scope import select

        return select(config)
    if atom == "read_factory_stuck":
        from lokay.proc.read_factory_stuck import read

        return read(config)
    if atom == "harvest_factory_children":
        from lokay.proc.harvest_factory_children import harvest

        return harvest(config, scope, up.get("read_factory_stuck") or {})
    if atom == "persist_factory_stuck":
        from lokay.proc.persist_factory_stuck import persist

        return persist(
            up.get("read_factory_stuck") or {}, up.get("harvest_factory_children") or {}
        )
    if atom == "create_factory_pass_dir":
        from lokay.proc.create_factory_pass_dir import create

        return create(config)
    if atom == "select_factory_survey_repos":
        from lokay.proc.select_factory_survey_repos import select

        return select(config, scope, workspace)
    if atom == "build_factory_begin_state":
        from lokay.proc.build_factory_begin_state import build

        return build(
            config,
            scope,
            ledger,
            workspace,
            up.get("select_factory_survey_repos") or {},
        )
    if atom == "build_factory_working_state":
        from lokay.proc.build_factory_working_state import build

        return build(ledger)
    if atom == "persist_factory_begin_state":
        from lokay.proc.persist_factory_begin_state import persist

        return persist(workspace, built, working)
    if atom == "classify_factory_begin_terminal":
        from lokay.proc.classify_factory_begin_terminal import classify

        return classify(
            lease,
            up.get("reinspect_factory_lease") or {},
            up.get("run_factory_preflight") or {},
            up.get("classify_factory_mode") or {},
        )
    if atom.startswith("build_factory_begin_terminal_"):
        from lokay.proc import build_factory_begin_terminal as terminals

        builders = {
            "ready": lambda: terminals.ready(config, ledger, workspace, built),
            "offline": lambda: terminals.offline(config, scope),
            "mode_not_live": terminals.mode_not_live,
            "preflight_failed": terminals.preflight_failed,
        }
        return builders[atom.removeprefix("build_factory_begin_terminal_")]()
    if atom == "select_factory_begin_terminal":
        from lokay.proc.select_factory_begin_terminal import select

        return select(
            [
                up.get(f"build_factory_begin_terminal_{x}") or {}
                for x in ("preflight_failed", "mode_not_live", "offline", "ready")
            ]
        )
    return None
