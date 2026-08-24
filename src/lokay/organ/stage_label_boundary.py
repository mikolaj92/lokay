"""Fala bindings for authored one-issue stage transition."""

from typing import Any


def handle_stage_label(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    prepared = up.get("prepare_stage_transition") or {}
    issue = up.get("read_stage_issue") or {}
    classified = up.get("classify_stage_issue") or {}
    removed = up.get("record_stage_removal") or {}
    added = up.get("add_stage_labels_effect") or {}
    if atom == "prepare_stage_transition":
        from lokay.proc.prepare_stage_transition import prepare

        return prepare(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            repo=str(inputs.get("repo") or ""),
            issue=int(inputs.get("issue") or 0),
            stage=str(inputs.get("stage") or ""),
            receipt=bool(inputs.get("receipt")),
            comment=str(inputs.get("comment") or ""),
        )
    if atom == "read_stage_issue":
        from lokay.proc.read_stage_issue import read

        return read(prepared, config_path=str(inputs.get("config_path") or "") or None)
    if atom == "classify_stage_issue":
        from lokay.proc.classify_stage_issue import classify

        return classify(issue, prepared)
    if atom == "remove_stage_labels_effect":
        from lokay.proc.remove_stage_labels_effect import remove

        return remove(prepared)
    if atom == "record_stage_removal":
        from lokay.proc.record_stage_removal import record

        return record(classified, up.get("remove_stage_labels_effect") or {})
    if atom == "add_stage_labels_effect":
        from lokay.proc.add_stage_labels_effect import add

        return add(prepared, removed)
    if atom == "comment_stage_receipt_effect":
        from lokay.proc.comment_stage_receipt_effect import comment

        return comment(prepared)
    if atom == "stage_label_terminal":
        from lokay.proc.stage_label_terminal import terminal

        return terminal(
            prepared,
            issue,
            classified,
            removed,
            added,
            up.get("comment_stage_receipt_effect") or {},
        )
    return None
