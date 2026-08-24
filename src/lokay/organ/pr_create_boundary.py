"""Fala bindings for authored one-PR publication."""

from pathlib import Path
from typing import Any


def handle_pr_create(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    request = up.get("prepare_pr_create_request") or {}
    existing = up.get("record_existing_delivery_pr") or {}
    issue = up.get("read_pr_create_issue") or {}
    classified = up.get("classify_pr_create_issue") or {}
    if atom == "prepare_pr_create_request":
        import argparse

        from lokay.proc._common import load_cfg, mutations_allowed
        from lokay.proc.prepare_pr_create_request import prepare

        cfg = load_cfg(
            argparse.Namespace(
                config=str(inputs.get("config_path") or "") or None,
                live=bool(inputs.get("live")),
            )
        )
        body = str(inputs.get("body") or "")
        body_file = str(inputs.get("body_file") or "")
        if body_file:
            body = Path(body_file).read_text(encoding="utf-8")
        return prepare(
            repo=str(inputs.get("repo") or ""),
            issue=int(inputs["issue"]) if inputs.get("issue") is not None else None,
            title=str(inputs.get("title") or ""),
            body=body,
            head=str(inputs.get("head") or ""),
            base=str(inputs.get("base") or "main"),
            branch_prefix=cfg.branch_prefix,
            live=mutations_allowed(live_flag=bool(inputs.get("live")), cfg=cfg),
        )
    if atom == "find_existing_delivery_pr":
        from lokay.proc.find_existing_delivery_pr import find

        return find(request, live=bool(request.get("live")))
    if atom == "record_existing_delivery_pr":
        from lokay.proc.record_existing_delivery_pr import record

        return record(up.get("find_existing_delivery_pr") or {})
    if atom == "read_pr_create_issue":
        import argparse

        from lokay.proc._common import load_cfg
        from lokay.proc.read_pr_create_issue import read

        cfg = load_cfg(
            argparse.Namespace(
                config=str(inputs.get("config_path") or "") or None,
                live=bool(inputs.get("live")),
            )
        )
        return read(request, config=cfg, live=bool(request.get("live")))
    if atom == "classify_pr_create_issue":
        from lokay.proc.classify_pr_create_issue import classify

        return classify(existing, issue)
    if atom == "create_pull_request_effect":
        from lokay.proc.create_pull_request_effect import create

        return create(request, live=bool(request.get("live")))
    if atom == "pr_create_terminal":
        from lokay.proc.pr_create_terminal import terminal

        return terminal(
            request,
            existing,
            issue,
            classified,
            up.get("create_pull_request_effect") or {},
        )
    return None
