"""Remove one orphan configured-ready label, or report the planned effect."""

import argparse
from lokay.gh_issues import remove_issue_labels
from lokay.proc._common import load_cfg, runner


def remove(selected: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    live = bool(selected.get("mutations_allowed"))
    remove_issue_labels(
        runner(cfg),
        selected["repo"],
        int(selected["number"]),
        [str(cfg.ready_label)],
        live=live,
    )
    return {
        **selected,
        "ok": True,
        "route": "removed" if live else "planned",
        "applied": live,
    }
