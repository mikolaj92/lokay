"""One bounded semantic retry when the coding diff exceeds localize scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import list_changed_paths
from lokay.localize import LOCALIZE_REL_PATH, extract_issue_file_paths, write_localize_file
from lokay.localize_agent import build_localization_with_agent
from lokay.proc._common import load_cfg, mutations_allowed, runner, semantic_agent_allowed
from lokay.proc.assert_real_diff import _off_goal_paths
from lokay.runner import Runner, git_spec


_FACTORY_BEGIN = "src/lokay/proc/factory_begin.py"


def _issue_explicitly_names_factory_begin(issue_json: str) -> bool:
    if not issue_json:
        return False
    payload = json.loads(Path(issue_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("issue-json must be an object")
    return _FACTORY_BEGIN in extract_issue_file_paths(str(payload.get("body") or ""))


def _restore_factory_begin(run: Runner, root: Path, base: str, *, live: bool) -> None:
    run.run_checked(
        git_spec(
            ["restore", "--source", base, "--staged", "--worktree", "--", _FACTORY_BEGIN],
            cwd=root,
        ),
        live=live,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-relocalize-off-goal")
    p.add_argument("--config")
    p.add_argument("--live", action="store_true")
    p.add_argument("--worktree", required=True)
    p.add_argument("--base", default="origin/main")
    p.add_argument("--issue-json", default="")
    args = p.parse_args(argv)
    root = Path(args.worktree).resolve()
    evidence = root / LOCALIZE_REL_PATH
    if not root.is_dir() or not evidence.is_file():
        return emit_exit(ok(skipped=True, reason="no_localize", worktree=str(root)))
    run = runner()
    try:
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        localized = [str(p).removeprefix("./").rstrip("/") for p in payload.get("paths", [])]
        changed = list_changed_paths(run, root, base=args.base)
        factory_off_goal = (
            _FACTORY_BEGIN in changed
            and not _issue_explicitly_names_factory_begin(args.issue_json)
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), reason="invalid_localize", worktree=str(root)))

    cfg = load_cfg(args)
    live = False
    if factory_off_goal:
        try:
            live = mutations_allowed(live_flag=args.live, cfg=cfg)
            _restore_factory_begin(run, root, args.base, live=live)
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc), reason="restore_failed", worktree=str(root)))
        changed = [path for path in changed if path != _FACTORY_BEGIN]

    off_goal = _off_goal_paths(changed, localized)
    if not off_goal:
        return emit_exit(
            ok(
                skipped=not factory_off_goal,
                reason="factory_begin_restored" if factory_off_goal else "on_goal",
                planned=bool(factory_off_goal and not live),
                restored_paths=[_FACTORY_BEGIN] if factory_off_goal else [],
                worktree=str(root),
            )
        )

    execute = semantic_agent_allowed(cfg, live_flag=args.live)
    seed = (
        "One bounded relocalization retry. The coding diff changed these paths outside the "
        f"original scope: {off_goal}. Original scope: {localized}. Return only paths that are "
        "genuinely necessary to implement the same issue; do not approve unrelated residue."
    )
    loc = build_localization_with_agent(
        runner=runner(cfg) if execute else None,
        config=cfg,
        execute=execute,
        worktree=root,
        seed_text=seed,
        extra_paths=localized,
        max_paths=40,
    )
    approved = [p for p in off_goal if p in loc.paths]
    if not approved or not execute or (loc.semantic or {}).get("source") != "agent":
        return emit_exit(
            ok(
                skipped=True,
                reason="off_goal_not_approved",
                off_goal_paths=off_goal,
                semantic=loc.semantic,
                worktree=str(root),
            )
        )
    if not factory_off_goal:
        live = mutations_allowed(live_flag=args.live, cfg=cfg)
    merged = tuple(dict.fromkeys([*localized, *approved]))
    if live:
        loc = type(loc)(
            paths=merged,
            source=loc.source,
            seed_paths=loc.seed_paths,
            matched_tokens=loc.matched_tokens,
            notes=tuple([*loc.notes, "One bounded off-goal relocalization approved required paths."]),
            worktree=loc.worktree,
            semantic=loc.semantic,
        )
        write_localize_file(root, loc)
    return emit_exit(
        ok(
            planned=not live,
            retried=True,
            approved_paths=approved,
            paths=list(merged),
            semantic=loc.semantic,
            restored_paths=[_FACTORY_BEGIN] if factory_off_goal else [],
            worktree=str(root),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
