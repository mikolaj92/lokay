"""One job: remove legacy ai:ready when work:ready is absent."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_labeled_issues, remove_issue_labels
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner

MINI_MILL_REPO = "mikolaj92/lokay"
WORK_READY_LABEL = "work:ready"


def run_ready_hygiene(*, config_path: str | None, live: bool) -> dict[str, Any]:
    args = argparse.Namespace(config=config_path, live=live)
    cfg = load_cfg(args)
    apply = mutations_allowed(live_flag=live, cfg=cfg)
    cleaned: list[dict[str, Any]] = []
    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        issues = list_labeled_issues(
            runner(cfg), cfg, repo, label=cfg.ready_label, live=apply
        )
        for issue in issues:
            if WORK_READY_LABEL in issue.labels:
                continue
            remove_issue_labels(
                runner(cfg), repo.name, issue.number, [cfg.ready_label], live=apply
            )
            cleaned.append({"repo": repo.name, "issue": issue.number})
    return ok(planned=not apply, applied=apply, cleaned=cleaned, cleaned_count=len(cleaned))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-ready-hygiene")
    add_config_live(parser)
    args = parser.parse_args(argv)
    try:
        payload = run_ready_hygiene(config_path=args.config, live=bool(args.live))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
