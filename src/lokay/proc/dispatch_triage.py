"""One job: run planned inbox triage child paths (issue_triage)."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.passkit import io as pass_io
from lokay.proc._common import add_config_live


def run_dispatch_triage(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    remaining_inbox = int(working.get("remaining_inbox") or 0)
    inbox_by_repo = dict(working.get("inbox_by_repo") or {})
    ran = 0

    if not live:
        pass_io.write_json(pass_io.working_path(pass_dir), working)
        return ok(pass_dir=pass_dir, ran=0, skipped=True, reason="dry_run")

    for target in list(plan.get("triage_targets") or []):
        repo_name = str(target["repo"])
        num = int(target["issue"])
        try:
            tri = run_path(
                path_id="issue_triage",
                repo=repo_name,
                issue=num,
                config_path=config_path,
                live=True,
            )
            actions.append(
                {"step": "issue_triage", "repo": repo_name, "issue": num, **tri}
            )
            # Live progress means a real label mutation, never merely a
            # successfully completed graph or a decision=skip no-op.
            decision = tri.get("decision")
            skipped = (
                tri.get("skipped")
                or (
                    isinstance(decision, dict)
                    and decision.get("decision") == "skip"
                )
            )
            if tri.get("ok") and tri.get("applied") is True and not skipped:
                progress += 1
                remaining_inbox = max(0, remaining_inbox - 1)
                inbox_by_repo[repo_name] = max(
                    0, int(inbox_by_repo.get(repo_name) or 0) - 1
                )
            ran += 1
        except Exception as exc:
            actions.append(
                {
                    "step": "issue_triage",
                    "repo": repo_name,
                    "issue": num,
                    "ok": False,
                    "engine": "fala",
                    "error": f"Fala path failed (no atom super-fallback): {exc}",
                }
            )
            ran += 1

    working.update(
        {
            "actions": actions,
            "progress": progress,
            "remaining_inbox": remaining_inbox,
            "inbox_by_repo": inbox_by_repo,
        }
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return ok(pass_dir=pass_dir, ran=ran)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-dispatch-triage")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_dispatch_triage(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
