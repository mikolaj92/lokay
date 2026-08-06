from __future__ import annotations

import argparse
import json
import sys

from lokay import __version__
from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.compose.tick import compose_tick
from lokay.config import load_config, starter_config_text


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_init(args: argparse.Namespace) -> int:
    from pathlib import Path

    target = Path(args.config or Path.home() / ".lokay" / "config.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not args.force:
        print(f"config already exists: {target} (use --force)", file=sys.stderr)
        return 1
    target.write_text(
        starter_config_text(assignee=args.assignee, repo=args.repo, clone=args.clone),
        encoding="utf-8",
    )
    print(f"wrote {target}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    errors = cfg.validate()
    _print(
        {
            "config": str(cfg.config_path),
            "mode": cfg.mode,
            "repos": [r.name for r in cfg.repos],
            "executor": cfg.grok_command,
            "executor_enabled": cfg.executor_enabled,
            "ok": not errors,
            "errors": errors,
            "unix": "see docs/UNIX.md — prefer atomic lokay-* processes",
        }
    )
    return 1 if errors else 0


def cmd_tick(args: argparse.Namespace) -> int:
    payload = compose_tick(config_path=args.config, live=bool(args.live))
    _print(payload)
    return 0 if payload.get("ok") else 1


def cmd_run(args: argparse.Namespace) -> int:
    payload = compose_issue_to_pr(
        config_path=args.config,
        repo=args.repo,
        issue_number=int(args.issue),
        live=bool(args.live),
    )
    _print(payload)
    return 0 if payload.get("ok") else 1


def cmd_path(args: argparse.Namespace) -> int:
    from lokay.graph_run import describe_package, run_path

    if args.describe:
        _print({"ok": True, **describe_package(args.package)})
        return 0
    payload = run_path(
        path_id=args.path,
        repo=args.repo,
        issue=args.issue,
        config_path=args.config,
        live=bool(args.live),
        package_path=args.package,
    )
    _print(payload)
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lokay",
        description="Umbrella CLI. Prefer atomic lokay-* processes (docs/UNIX.md).",
    )
    p.add_argument("--version", action="version", version=f"lokay {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_config(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--config", help="config.yaml path")

    init = sub.add_parser("init", help="Write starter config")
    add_config(init)
    init.add_argument("--force", action="store_true")
    init.add_argument("--assignee", default="mikolaj92")
    init.add_argument("--repo")
    init.add_argument("--clone")
    init.set_defaults(func=cmd_init)

    val = sub.add_parser("validate", help="Validate config")
    add_config(val)
    val.set_defaults(func=cmd_validate)

    t = sub.add_parser("tick", help="Composer: one intake+triage cycle")
    add_config(t)
    t.add_argument("--live", action="store_true")
    t.set_defaults(func=cmd_tick)

    r = sub.add_parser("run", help="Run Fala issue_to_pr graph for one issue")
    add_config(r)
    r.add_argument("--repo", required=True)
    r.add_argument("--issue", required=True, type=int)
    r.add_argument("--live", action="store_true")
    r.set_defaults(func=cmd_run)

    g = sub.add_parser("path", help="Run/describe Fala correlation path")
    add_config(g)
    g.add_argument("--path", default="issue_to_pr")
    g.add_argument("--repo")
    g.add_argument("--issue", type=int)
    g.add_argument("--live", action="store_true")
    g.add_argument("--describe", action="store_true")
    g.add_argument("--package")
    g.set_defaults(func=cmd_path)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
