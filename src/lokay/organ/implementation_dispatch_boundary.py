"""Fala bindings for one serial implementation dispatch."""

from typing import Any


def handle_implementation_dispatch(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    if atom == "select_implementation_candidate":
        from lokay.proc.select_implementation_candidate import select

        return select(pass_dir=pass_dir)
    if atom == "inspect_implementation_mutex":
        from lokay.proc.inspect_implementation_mutex import inspect

        return inspect(up.get("select_implementation_candidate") or {})
    if atom == "select_mutex_outcome":
        from lokay.proc.select_mutex_outcome import select

        return select(
            up.get("select_implementation_candidate") or {},
            up.get("inspect_implementation_mutex") or {},
        )
    if atom == "keep_implementation_candidate":
        from lokay.proc.record_dispatch_keep import apply

        return apply(pass_dir=pass_dir, candidate=up.get("select_mutex_outcome") or {})
    if atom == "verify_selected_issue_ready":
        from lokay.proc.verify_selected_issue_ready import verify

        return verify(up.get("select_mutex_outcome") or {}, config_path=config)
    if atom == "select_ready_outcome":
        from lokay.proc.select_ready_outcome import select

        return select(
            up.get("select_mutex_outcome") or {},
            up.get("verify_selected_issue_ready") or {},
        )
    if atom == "drop_stale_implementation_candidate":
        from lokay.proc.record_dispatch_drop import apply

        return apply(
            pass_dir=pass_dir,
            candidate=up.get("verify_selected_issue_ready") or {},
            gate=up.get("verify_selected_issue_ready") or {},
        )
    if atom == "launch_issue_to_pr":
        from lokay.proc.launch_issue_to_pr import launch

        return launch(up.get("select_ready_outcome") or {}, config_path=config)
    if atom == "select_launch_route":
        from lokay.proc.select_launch_route import select

        return select(
            up.get("select_ready_outcome") or {}, up.get("launch_issue_to_pr") or {}
        )
    if atom == "record_dispatch_success":
        from lokay.proc.record_dispatch_success import apply

        return apply(pass_dir=pass_dir, launched=up.get("select_launch_route") or {})
    if atom == "record_dispatch_failure":
        from lokay.proc.record_dispatch_failure import apply

        return apply(pass_dir=pass_dir, launched=up.get("select_launch_route") or {})
    if atom == "select_dispatch_outcome":
        from lokay.proc.select_dispatch_outcome import select

        return select(
            up.get("record_dispatch_success") or {},
            up.get("record_dispatch_failure") or {},
        )
    if atom == "persist_dispatch_stuck":
        from lokay.proc.persist_dispatch_stuck import apply

        return apply(pass_dir=pass_dir)
    if atom == "label_blocked_dispatch":
        from lokay.proc._common import load_cfg, mutations_allowed, runner
        from lokay.gh_issues import add_issue_labels
        import argparse

        failure = up.get("select_dispatch_outcome") or {}
        cfg = load_cfg(argparse.Namespace(config=config))
        live = mutations_allowed(live_flag=bool(inputs.get("live")), cfg=cfg)
        add_issue_labels(
            runner(),
            str(failure["repo"]),
            int(failure["issue"]),
            [str(cfg.blocked_label)],
            live=live,
        )
        return {
            "ok": True,
            "applied": live,
            "repo": failure["repo"],
            "issue": failure["issue"],
            "labels": [cfg.blocked_label],
        }
    if atom == "persist_blocked_dispatch":
        from lokay.proc.persist_blocked_dispatch import apply

        return apply(
            pass_dir=pass_dir,
            failure=up.get("select_dispatch_outcome") or {},
            label=up.get("label_blocked_dispatch") or {},
        )
    if atom == "select_blocked_dispatch":
        from lokay.proc.select_blocked_dispatch import select

        return select(
            up.get("persist_blocked_dispatch") or {},
            up.get("select_dispatch_outcome") or {},
        )
    if atom == "park_plan_only_dispatch":
        from lokay.proc._common import run_proc
        from lokay.proc import unbounded_park

        f = up.get("select_blocked_dispatch") or {}
        args = (
            (["--config", config] if config else [])
            + (["--live"] if inputs.get("live") else [])
            + ["--repo", str(f["repo"]), "--issue", str(f["issue"])]
        )
        return run_proc(unbounded_park.main, args)
    if atom == "write_dispatch_receipt":
        from lokay.proc.write_dispatch_receipt import write

        return write(pass_dir=pass_dir)
    if atom == "summarize_implementation_dispatch":
        from lokay.proc.summarize_implementation_dispatch import summarize

        return summarize(pass_dir=pass_dir)
    return None
