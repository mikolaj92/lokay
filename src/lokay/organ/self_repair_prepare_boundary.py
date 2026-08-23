"""Fala bindings for explicit self-repair worktree preparation."""

from typing import Any


def _up(up, name):
    value = up.get(name) or {}
    return value if value.get("ok") else {}


def _first(up, *names):
    for name in names:
        value = _up(up, name)
        if value:
            return value
    return {}


def handle_self_repair_prepare(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    fingerprint = str(inputs.get("fingerprint") or "")
    if atom == "resolve_self_repair_checkout":
        from lokay.proc.resolve_self_repair_checkout import resolve

        return resolve(config_path=config, fingerprint=fingerprint)
    checkout = _up(up, "resolve_self_repair_checkout")
    if atom == "check_self_repair_mutation_gate":
        from lokay.proc.check_self_repair_mutation_gate import check

        return check(checkout, config_path=config, live=live)
    gate = _up(up, "check_self_repair_mutation_gate")
    if atom == "verify_self_repair_origin":
        from lokay.proc.verify_self_repair_origin import verify

        return verify(gate)
    if atom == "select_self_repair_origin_gate":
        return _first(
            up, "verify_self_repair_origin", "check_self_repair_mutation_gate"
        )
    origin = _up(up, "select_self_repair_origin_gate")
    if atom == "fetch_self_repair_main":
        from lokay.proc.fetch_self_repair_main import fetch

        return fetch(origin)
    if atom == "select_self_repair_fetch_gate":
        return _first(up, "fetch_self_repair_main", "select_self_repair_origin_gate")
    fetched = _up(up, "select_self_repair_fetch_gate")
    if atom == "find_published_self_repair":
        from lokay.proc.find_published_self_repair import find

        return find(fetched)
    if atom == "select_self_repair_publish_gate":
        return _first(
            up,
            "find_published_self_repair",
            "select_self_repair_fetch_gate",
            "check_self_repair_mutation_gate",
        )
    published = _up(up, "select_self_repair_publish_gate")
    if atom == "read_self_repair_base":
        from lokay.proc.read_self_repair_base import read

        return read(published)
    if atom == "select_self_repair_base_gate":
        return _first(up, "read_self_repair_base", "select_self_repair_publish_gate")
    base = _up(up, "select_self_repair_base_gate")
    if atom == "inspect_self_repair_ownership":
        from lokay.proc.inspect_self_repair_ownership import inspect

        return inspect(base)
    if atom == "select_self_repair_ownership_gate":
        return _first(
            up, "inspect_self_repair_ownership", "select_self_repair_base_gate"
        )
    owned = _up(up, "select_self_repair_ownership_gate")
    if atom == "inspect_self_repair_changes":
        from lokay.proc.inspect_self_repair_changes import inspect

        return inspect(owned)
    if atom == "select_self_repair_changes_gate":
        return _first(
            up, "inspect_self_repair_changes", "select_self_repair_ownership_gate"
        )
    changes = _up(up, "select_self_repair_changes_gate")
    if atom == "validate_self_repair_change_shape":
        from lokay.proc.validate_self_repair_change_shape import validate

        return validate(changes)
    if atom == "select_self_repair_shape_gate":
        return _first(
            up, "validate_self_repair_change_shape", "select_self_repair_changes_gate"
        )
    shape = _up(up, "select_self_repair_shape_gate")
    if atom == "inspect_self_repair_commit":
        from lokay.proc.inspect_self_repair_commit import inspect

        return inspect(shape)
    if atom == "select_self_repair_commit_gate":
        return _first(up, "inspect_self_repair_commit", "select_self_repair_shape_gate")
    commit = _up(up, "select_self_repair_commit_gate")
    if atom == "validate_self_repair_commit":
        from lokay.proc.validate_self_repair_commit import validate

        return validate(commit)
    if atom == "select_self_repair_commit_validation_gate":
        return _first(
            up, "validate_self_repair_commit", "select_self_repair_commit_gate"
        )
    validated = _up(up, "select_self_repair_commit_validation_gate")
    if atom == "inspect_self_repair_ancestry":
        from lokay.proc.inspect_self_repair_ancestry import inspect

        return inspect(validated)
    if atom == "select_self_repair_worktree_route":
        return _first(
            up,
            "inspect_self_repair_ancestry",
            "select_self_repair_commit_validation_gate",
            "select_self_repair_shape_gate",
            "select_self_repair_changes_gate",
            "select_self_repair_ownership_gate",
            "select_self_repair_base_gate",
        )
    route = _up(up, "select_self_repair_worktree_route")
    if atom == "remove_self_repair_worktree":
        from lokay.proc.remove_self_repair_worktree import remove

        return remove(route)
    if atom == "select_self_repair_remove_outcome":
        outcome = _first(
            up, "remove_self_repair_worktree", "select_self_repair_worktree_route"
        )
        return (
            {**outcome, "route": "create_requested"}
            if outcome.get("route") in {"create", "removed"}
            else outcome
        )
    removed = _up(up, "select_self_repair_remove_outcome")
    if atom == "create_self_repair_worktree":
        from lokay.proc.create_self_repair_worktree import create

        return create(removed)
    if atom == "select_self_repair_prepare_result":
        from lokay.proc.select_self_repair_prepare_result import select

        return select(
            checkout,
            gate,
            published,
            base,
            route,
            removed,
            _up(up, "create_self_repair_worktree"),
        )
    if atom == "summarize_self_repair_prepare":
        from lokay.proc.summarize_self_repair_prepare import summarize

        return summarize(up.get("select_self_repair_prepare_result") or {})
    return None
