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
    config = up.get("load_factory_config") or {}
    scope = up.get("select_factory_scope") or {}
    ledger = up.get("read_factory_stuck") or {}
    workspace = up.get("create_factory_pass_dir") or {}
    begin = up.get("build_factory_begin_state") or {}
    working = up.get("build_factory_working_state") or {}
    seeded = up.get("seed_factory_occupancy") or working
    attached = up.get("attach_factory_stuck") or {}
    if atom == "probe_factory_host":
        from lokay.proc.probe_factory_host import probe

        return probe()
    if atom == "load_factory_config":
        from lokay.proc.load_factory_config import load

        return load(config_path=config_path, live=live)
    if atom == "select_factory_scope":
        from lokay.proc.select_factory_scope import select

        return select(config)
    if atom == "read_factory_stuck":
        from lokay.proc.read_factory_stuck import read

        return read(config)
    if atom == "create_factory_pass_dir":
        from lokay.proc.create_factory_pass_dir import create

        return create(config)
    if atom == "build_factory_begin_state":
        from lokay.proc.build_factory_begin_state import build

        return build(config, scope, ledger, workspace)
    if atom == "build_factory_working_state":
        from lokay.proc.build_factory_working_state import build

        return build(ledger)
    if atom == "seed_factory_occupancy":
        from lokay.proc.seed_factory_occupancy import run

        return run(working)
    if atom == "attach_factory_stuck":
        from lokay.proc.attach_factory_stuck import attach

        return attach(begin, seeded, ledger)
    if atom == "persist_factory_begin_state":
        from lokay.proc.persist_factory_begin_state import persist

        return persist(workspace, attached)
    if atom == "persist_factory_working_state":
        from lokay.proc.persist_factory_working_state import persist

        return persist(workspace, attached)
    if atom == "persist_factory_tick":
        from lokay.proc.persist_factory_tick import persist

        return persist(workspace, attached, up.get("probe_factory_host") or {}, ledger)
    if atom == "classify_leftover_remaining":
        from lokay.pass_receipt import read_pass_receipt
        from lokay.proc.classify_leftover_remaining import classify_receipt

        state_path = str(config.get("state_path") or "") or None
        return classify_receipt(read_pass_receipt(state_path=state_path))
    if atom == "merge_leftover_remaining":
        from lokay.proc.merge_leftover_remaining import merge

        persisted = (
            up.get("persist_factory_tick")
            or up.get("persist_factory_working_state")
            or workspace
        )
        return merge(
            pass_dir=str(persisted.get("pass_dir") or workspace.get("pass_dir") or ""),
            state_path=str(config.get("state_path") or "") or None,
        )
    return None
