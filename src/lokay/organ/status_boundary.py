"""Fala bindings for authored read-only status snapshot."""

from typing import Any


def handle_status(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = up.get("read_status_config") or {}
    if atom == "read_status_config":
        from lokay.proc.read_status_config import read

        return read(
            config_path=str(inputs.get("config_path") or "") or None,
            preflight=bool(inputs.get("preflight")),
            full=bool(inputs.get("full")),
        )
    if atom == "classify_status_readiness":
        from lokay.proc.classify_status_readiness import classify

        return classify(config)
    if atom == "read_status_clone_facts":
        from lokay.proc.read_status_clone_facts import read

        return read(config)
    if atom == "read_status_lease":
        from lokay.proc.read_status_lease import read

        return read(config)
    if atom == "read_status_pass_receipt":
        from lokay.proc.read_status_pass_receipt import read

        return read(config)
    if atom == "read_status_work_units":
        from lokay.proc.read_status_work_units import read

        return read(config)
    if atom == "describe_status_graphs":
        from lokay.proc.describe_status_graphs import describe

        return describe()
    if atom == "run_status_preflight":
        from lokay.proc.run_status_preflight import run

        return run(config)
    if atom == "record_status_preflight":
        from lokay.proc.record_status_preflight import record

        return record(config, up.get("run_status_preflight") or {})
    if atom == "reduce_status_snapshot":
        from lokay.proc.reduce_status_snapshot import reduce

        return reduce(
            config,
            up.get("classify_status_readiness") or {},
            up.get("read_status_clone_facts") or {},
            up.get("read_status_lease") or {},
            up.get("read_status_pass_receipt") or {},
            up.get("read_status_work_units") or {},
            up.get("describe_status_graphs") or {},
            up.get("record_status_preflight") or {},
        )
    if atom == "status_snapshot_terminal":
        from lokay.proc.status_snapshot_terminal import terminal

        return terminal(up.get("reduce_status_snapshot") or {})
    return None
