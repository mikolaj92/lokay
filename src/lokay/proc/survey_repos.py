"""Thin bridge: survey_prs then survey_inbox then survey_ready (legacy CLI).

Parent ``factory_pass`` conducts those atoms as separate Fala nodes.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live
from lokay.proc.survey_inbox import run_survey_inbox
from lokay.proc.survey_prs import run_survey_prs
from lokay.proc.survey_ready_subflow import run as run_survey_ready


def run_survey_repos(
    *, pass_dir: str, config_path: str | None, live: bool
) -> dict[str, Any]:
    prs = run_survey_prs(pass_dir=pass_dir, config_path=config_path, live=live)
    if not prs.get("ok"):
        return prs
    inbox = run_survey_inbox(pass_dir=pass_dir, config_path=config_path, live=live)
    if not inbox.get("ok"):
        return inbox
    ready = run_survey_ready(pass_dir=pass_dir, config_path=config_path, live=live)
    if not ready.get("ok"):
        return ready
    return ok(
        pass_dir=pass_dir,
        survey_errors=ready.get("survey_errors"),
        remaining_inbox=inbox.get("remaining_inbox"),
        remaining_ready=ready.get("remaining_ready"),
        remaining_prs=prs.get("remaining_prs"),
        actionable_prs=prs.get("actionable_prs"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-survey-repos")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_repos(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
