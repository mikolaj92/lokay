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
    if atom == "probe_factory_host":
        from lokay.proc.probe_factory_host import probe

        return probe()
    if atom == "load_factory_config":
        from lokay.proc.load_factory_config import load

        return load(config_path=config_path, live=live)
    if atom == "select_factory_scope":
        from lokay.proc.select_factory_scope import select

        return select(up.get("load_factory_config") or {})
    if atom == "create_factory_pass_dir":
        from lokay.proc.create_factory_pass_dir import create

        return create(up.get("load_factory_config") or {})
    if atom == "persist_factory_begin_state":
        from lokay.proc.persist_factory_begin_state import persist

        return persist(
            up.get("create_factory_pass_dir") or {},
            up.get("load_factory_config") or {},
            up.get("select_factory_scope") or {},
            up.get("probe_factory_host") or {},
        )
    return None
