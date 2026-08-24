"""Fala bindings for authored localization execution."""

from typing import Any


def handle_localize(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    request = up.get("prepare_localization_request") or {}
    inspected = up.get("inspect_existing_localization") or {}
    route = up.get("classify_localization_route") or {}
    agent_request = up.get("build_localization_agent_request") or {}
    config_path = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_localization_request":
        from lokay.proc.prepare_localization_request import prepare

        return prepare(
            worktree=str(inputs.get("worktree") or ""),
            repo=str(inputs.get("repo") or ""),
            issue_raw=dict(inputs.get("issue_raw") or {}),
            plan=dict(inputs.get("plan") or {}),
            checks_text=str(inputs.get("checks_text") or ""),
            review=inputs.get("review") or {},
            extra_paths=list(inputs.get("extra_paths") or []),
            max_paths=int(inputs.get("max_paths") or 40),
            rel_path=str(inputs.get("rel_path") or ".lokay/localize.json"),
        )
    if atom == "inspect_existing_localization":
        from lokay.proc.inspect_existing_localization import inspect

        return inspect(request)
    if atom == "classify_localization_route":
        import argparse

        from lokay.proc._common import load_cfg, semantic_agent_allowed
        from lokay.proc.classify_localization_route import classify

        allowed = False
        if config_path or live:
            cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
            allowed = semantic_agent_allowed(cfg, live_flag=live)
        return classify(request, inspected, agent_allowed=allowed)
    if atom == "build_explicit_localization":
        from lokay.proc.build_explicit_localization import build

        return build(request, inspected, route)
    if atom == "build_deterministic_localization":
        from lokay.proc.build_deterministic_localization import build

        return build(request)
    if atom == "build_localization_agent_request":
        from lokay.proc.build_localization_agent_request import build

        return build(request, inspected, route)
    if atom in {"run_localization_agent", "retry_localization_agent"}:
        import argparse

        from lokay.proc._common import load_cfg
        from lokay.proc.run_localization_agent import run

        cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
        suffix = (
            str((up.get("build_localization_retry") or {}).get("feedback") or "")
            if atom.startswith("retry")
            else ""
        )
        return run(request, agent_request, config=cfg, prompt_suffix=suffix)
    if atom == "validate_localization_agent_json":
        from lokay.proc.validate_localization_agent_json import validate

        return validate(up.get("run_localization_agent") or {})
    if atom == "build_localization_retry":
        from lokay.proc.build_localization_retry import build

        return build(up.get("validate_localization_agent_json") or {})
    if atom == "validate_localization_retry_json":
        from lokay.proc.validate_localization_agent_json import validate

        return validate(up.get("retry_localization_agent") or {})
    if atom == "select_localization_candidate":
        from lokay.proc.select_localization_candidate import select

        return select(
            route,
            up.get("build_explicit_localization") or {},
            up.get("build_deterministic_localization") or {},
            up.get("validate_localization_agent_json") or {},
            up.get("validate_localization_retry_json") or {},
            up.get("run_localization_agent") or {},
            up.get("retry_localization_agent") or {},
        )
    if atom == "validate_localization_paths":
        from lokay.proc.validate_localization_paths import validate

        return validate(
            request,
            inspected,
            up.get("select_localization_candidate") or {},
            agent_request,
        )
    if atom == "write_localization_evidence":
        from lokay.proc.write_localization_evidence import write

        return write(request, up.get("validate_localization_paths") or {}, live=live)
    if atom == "localization_terminal":
        from lokay.proc.localization_terminal import terminal

        return terminal(
            up.get("write_localization_evidence") or {},
            up.get("select_localization_candidate") or {},
        )
    return None
