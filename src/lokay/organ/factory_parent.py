"""Parent factory_pass children: self_repair, PRs, leftover reap, issues."""

from typing import Any


def handle_factory_parent(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    del ctx

    def pass_dir() -> str:
        return str(
            (up.get("self_repair") or {}).get("pass_dir")
            or (up.get("auto_repair") or {}).get("pass_dir")
            or (up.get("factory_begin") or {}).get("pass_dir")
            or inputs.get("pass_dir")
            or ""
        )

    if atom == "self_repair":
        from lokay.proc.auto_repair import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "pr_triage":
        from lokay.proc.deal_with_prs import run

        opened = pass_dir()
        assert opened
        return run(
            pass_dir=opened,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "stale_worktree_reap":
        from lokay.proc.reap_after_merge import run

        opened = pass_dir()
        assert opened
        return run(
            pass_dir=opened,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "issue_triage":
        from lokay.proc.factory_issue_step import triage

        opened = pass_dir()
        assert opened
        return triage(
            pass_dir=opened,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "select_next_issue":
        from lokay.proc.factory_issue_step import select_next

        opened = pass_dir()
        assert opened
        return select_next(pass_dir=opened, triage=up.get("issue_triage") or {})

    if atom == "issue_to_pr":
        from lokay.proc.factory_issue_step import implement

        opened = pass_dir()
        assert opened
        return implement(
            pass_dir=opened,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            triage=up.get("issue_triage") or {},
            nxt=up.get("select_next_issue") or {},
        )

    if atom == "pr_triage_after":
        from lokay.proc.factory_issue_step import back_to_prs

        opened = pass_dir()
        assert opened
        return back_to_prs(
            pass_dir=opened,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "record_factory_idle":
        from lokay.proc.record_factory_idle import record

        return record(
            up.get("self_repair")
            or up.get("auto_repair")
            or up.get("classify_factory_idle")
            or {},
            config_path=str(inputs.get("config_path") or "") or None,
        )

    if atom == "factory_pass_terminal":
        from lokay.proc.factory_pass_terminal import terminal

        return terminal(
            up.get("self_repair")
            or up.get("auto_repair")
            or up.get("classify_factory_idle")
            or {},
            up.get("record_pass") or {},
            up.get("record_factory_idle") or {},
        )

    return None
