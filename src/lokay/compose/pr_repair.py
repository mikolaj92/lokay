"""Fala-only composition for repairing an open PR."""

from __future__ import annotations

import argparse
import json

from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.proc.admit_pr_repair import admit_live
from lokay.state import append_event



def compose_pr_repair(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
    review: dict | None = None,
    package_path: str | None = None,
) -> dict:
    if live and load_config(config_path).mode != "live":
        return {"ok": False, "error": "refusing live compose while config mode is not live"}
    if not branch:
        return {"ok": False, "error": "branch required for pr_repair"}

    admitted = admit_live(repo=repo, pr=pr_number, live=live)
    if str(admitted.get("route") or "") != "open":
        reason = str(admitted.get("reason") or "pr_already_merged")
        result = {
            "ok": True,
            "kind": "pr_repair",
            "engine": "admit",
            "planned": not live,
            "skipped": True,
            "reason": reason,
            "admit": admitted,
            "result": {
                "repo": repo,
                "pr": pr_number,
                "branch": branch,
                "repaired": False,
                "published": False,
                "terminal": reason,
                "reason": reason,
                "skipped": True,
                "head_sha": "",
            },
        }
        try:
            append_event(load_config(config_path).state_path, result)
        except Exception:
            pass
        return result

    result = run_path(
        path_id="pr_repair", repo=repo, pr=pr_number, branch=branch,
        config_path=config_path, live=live, package_path=package_path, extra_inputs={"review": review or {}},
    )
    result.update(kind="pr_repair", engine="fala", planned=not live, admit=admitted)
    try:
        append_event(load_config(config_path).state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-repair")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", required=True)
    p.add_argument("--review-json", default="")
    args = p.parse_args(argv)
    try:
        review = json.loads(args.review_json) if args.review_json else None
    except json.JSONDecodeError as exc:
        return emit_exit({"ok": False, "error": f"invalid --review-json: {exc}"})
    return emit_exit(compose_pr_repair(config_path=args.config, repo=args.repo, pr_number=args.pr, branch=args.branch, live=bool(args.live), review=review))


if __name__ == "__main__":
    raise SystemExit(main())
