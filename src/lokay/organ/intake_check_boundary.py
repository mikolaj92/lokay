"""Fala bindings for authored one mechanical intake check."""

import argparse
from typing import Any


def handle_intake_check(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    request = up.get("prepare_intake_check") or {}
    issue = up.get("read_intake_check_issue") or {}
    clone = up.get("resolve_intake_check_clone") or {}
    if atom == "prepare_intake_check":
        from lokay.proc.prepare_intake_check import prepare

        return prepare(
            repo=str(inputs.get("repo") or ""),
            issue=int(inputs.get("issue") or 0),
            check=str(inputs.get("check") or ""),
            merged_prs=[int(x) for x in inputs.get("merged_prs") or []],
            tracker_done=bool(inputs.get("tracker_done")),
            covering_prs=[str(x) for x in inputs.get("covering_prs") or []],
            live=bool(inputs.get("live")),
        )
    if atom in {"read_intake_check_issue", "resolve_intake_check_clone"}:
        from lokay.proc._common import load_cfg

        cfg = load_cfg(
            argparse.Namespace(
                config=str(inputs.get("config_path") or "") or None,
                live=bool(inputs.get("live")),
            )
        )
        if atom == "read_intake_check_issue":
            from lokay.proc.read_intake_check_issue import read

            return read(request, config=cfg)
        from lokay.proc.resolve_intake_check_clone import resolve

        return resolve(request, config=cfg)
    if atom == "classify_intake_check_route":
        from lokay.proc.classify_intake_check_route import classify

        return classify(request)
    if atom == "run_intake_open_check":
        from lokay.proc.run_intake_open_check import run

        return run(issue)
    if atom == "run_intake_superseded_check":
        from lokay.proc.run_intake_superseded_check import run

        return run(request, issue)
    if atom == "probe_intake_check_shape":
        from lokay.proc.probe_intake_check_shape import probe

        return probe(clone)
    if atom == "run_intake_shape_check":
        from lokay.proc.run_intake_shape_check import run

        return run(issue, up.get("probe_intake_check_shape") or {})
    if atom == "run_intake_satisfied_check":
        from lokay.proc.run_intake_satisfied_check import run

        return run(issue, clone)
    if atom == "run_intake_ambiguity_check":
        from lokay.proc.run_intake_ambiguity_check import run

        return run(issue)
    if atom == "parse_intake_covering_prs":
        from lokay.proc.parse_intake_covering_prs import parse

        return parse(request)
    if atom == "run_intake_duplicate_pr_check":
        from lokay.proc.run_intake_duplicate_pr_check import run

        return run(issue, up.get("parse_intake_covering_prs") or {})
    if atom == "select_intake_check_result":
        from lokay.proc.select_intake_check_result import select

        return select(
            up.get("run_intake_open_check") or {},
            up.get("run_intake_superseded_check") or {},
            up.get("run_intake_shape_check") or {},
            up.get("run_intake_satisfied_check") or {},
            up.get("run_intake_ambiguity_check") or {},
            up.get("run_intake_duplicate_pr_check") or {},
            up.get("parse_intake_covering_prs") or {},
        )
    if atom == "intake_check_terminal":
        from lokay.proc.intake_check_terminal import terminal

        return terminal(
            request, issue, clone, up.get("select_intake_check_result") or {}
        )
    return None
