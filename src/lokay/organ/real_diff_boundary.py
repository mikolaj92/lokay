"""Fala bindings for authored physical real-diff assertion."""

from typing import Any


def handle_real_diff(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    worktree = up.get("inspect_real_diff_worktree") or {}
    changed = up.get("read_real_diff_paths") or {}
    issue = up.get("read_real_diff_issue_scope") or {}
    presence = up.get("classify_ticket_scope_presence") or {}
    ticket = up.get("classify_ticket_scope_extra") or {}
    localize = up.get("read_real_diff_localize_scope") or {}
    scope = up.get("classify_localized_diff_scope") or {}
    kind = up.get("classify_real_diff_kind") or {}
    progress = up.get("classify_real_diff_progress") or {}
    if atom == "inspect_real_diff_worktree":
        from lokay.proc.inspect_real_diff_worktree import inspect

        return inspect(worktree=str(inputs.get("worktree") or ""))
    if atom == "read_real_diff_paths":
        from lokay.proc.read_real_diff_paths import read

        return read(worktree, base=str(inputs.get("base") or "origin/main"))
    if atom == "classify_real_diff_kind":
        from lokay.proc.classify_real_diff_kind import classify

        return classify(changed)
    if atom == "read_real_diff_localize_scope":
        from lokay.proc.read_real_diff_localize_scope import read

        return read(worktree)
    if atom == "read_real_diff_issue_scope":
        from lokay.proc.read_real_diff_issue_scope import read

        return read(issue_body=str(inputs.get("issue_body") or ""))
    if atom == "classify_ticket_scope_presence":
        from lokay.proc.classify_ticket_scope_presence import classify

        return classify(changed, issue)
    if atom == "classify_ticket_scope_extra":
        from lokay.proc.classify_ticket_scope_extra import classify

        return classify(changed, issue, presence)
    if atom == "classify_localized_diff_scope":
        from lokay.proc.classify_localized_diff_scope import classify

        return classify(changed, localize, ticket)
    if atom == "classify_real_diff_progress":
        from lokay.proc.classify_real_diff_progress import classify

        return classify(kind, scope)
    if atom == "real_diff_terminal":
        from lokay.proc.real_diff_terminal import terminal

        return terminal(
            worktree, changed, kind, localize, presence, ticket, scope, progress
        )
    return None
