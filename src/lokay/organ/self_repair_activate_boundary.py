"""Fala bindings for authored exact self-repair activation."""

from typing import Any


def handle_self_repair_activate(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    prepared = up.get("prepare_self_repair_activation") or {}
    status = up.get("read_canonical_checkout_status") or {}
    checkout = up.get("classify_canonical_checkout") or {}
    dirty = up.get("check_dirty_commit_on_origin") or {}
    fetched = up.get("record_canonical_fetch") or {}
    merged = up.get("record_recovery_fast_forward") or {}
    head = up.get("read_activated_head") or {}
    classified = up.get("classify_activated_head") or {}
    head_ancestor = up.get("record_recovery_head_ancestry") or {}
    origin_ancestor = up.get("check_recovery_ancestor_origin") or {}
    if atom == "prepare_self_repair_activation":
        from lokay.proc.prepare_self_repair_activation import prepare

        return prepare(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            commit=str(inputs.get("commit") or ""),
        )
    if atom == "read_canonical_checkout_status":
        from lokay.proc.read_canonical_checkout_status import read

        return read(prepared)
    if atom == "classify_canonical_checkout":
        from lokay.proc.classify_canonical_checkout import classify

        return classify(prepared, status)
    if atom == "check_dirty_commit_on_origin":
        from lokay.proc.check_dirty_commit_on_origin import check

        return check(prepared)
    if atom == "fetch_canonical_main":
        from lokay.proc.fetch_canonical_main import fetch

        return fetch(prepared)
    if atom == "fast_forward_recovery_commit":
        from lokay.proc.fast_forward_recovery_commit import merge

        return merge(prepared)
    if atom == "record_canonical_fetch":
        from lokay.proc.record_canonical_fetch import record

        return record(checkout, up.get("fetch_canonical_main") or {})
    if atom == "record_recovery_fast_forward":
        from lokay.proc.record_recovery_fast_forward import record

        return record(fetched, up.get("fast_forward_recovery_commit") or {})
    if atom == "read_activated_head":
        from lokay.proc.read_activated_head import read

        return read(prepared)
    if atom == "classify_activated_head":
        from lokay.proc.classify_activated_head import classify

        return classify(prepared, checkout, dirty, fetched, merged, head)
    if atom in {"check_recovery_ancestor_head", "check_recovery_ancestor_origin"}:
        from lokay.proc.check_recovery_ancestor import check

        return check(prepared, tip="HEAD" if atom.endswith("head") else "origin/main")
    if atom == "record_recovery_head_ancestry":
        from lokay.proc.record_recovery_head_ancestry import record

        return record(classified, up.get("check_recovery_ancestor_head") or {})
    if atom == "self_repair_activation_terminal":
        from lokay.proc.self_repair_activation_terminal import terminal

        return terminal(
            prepared,
            checkout,
            dirty,
            fetched,
            merged,
            head,
            classified,
            head_ancestor,
            origin_ancestor,
        )
    return None
