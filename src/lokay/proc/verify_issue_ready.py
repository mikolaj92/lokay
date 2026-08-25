"""Verify that one selected issue is still open work, not a human stop."""

from __future__ import annotations
import argparse
from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import get_issue
from lokay.proc._common import add_config_read, load_cfg, read_live, runner
from lokay.triage import is_open_work_issue


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-verify-issue-ready")
    add_config_read(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True, type=int)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=read_live(args))
    except Exception as exc:
        return emit_exit(err(str(exc), probe_failed=True))
    if issue is None:
        return emit_exit(err("issue not found", probe_failed=True))
    ready = is_open_work_issue(
        issue.labels or [],
        state=issue.state or "OPEN",
        blocked_label=cfg.blocked_label,
        needs_feedback_label=cfg.needs_feedback_label,
    )
    return emit_exit(
        ok(
            ready=ready,
            implementable=ready,
            issue=issue.to_dict(),
            reason="ready" if ready else "not_ready",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
