from __future__ import annotations

import argparse
import json
import sys

from lokay import __version__
from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.compose.mill import compose_mill
from lokay.compose.status import compose_status
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
            "repos": [r.name for r in cfg.active_repos()],
            "repos_disabled": [r.name for r in cfg.repos if not r.enabled],
            "repos_total": len(cfg.repos),
            "executor": cfg.agent_command,
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


def cmd_mill(args: argparse.Namespace) -> int:
    payload = compose_mill(
        config_path=args.config,
        live=bool(args.live),
        max_passes=int(args.max_passes),
    )
    _print(payload)
    return 0 if payload.get("ok") else 1


def cmd_status(args: argparse.Namespace) -> int:
    survey = not bool(getattr(args, "local", False))
    payload = compose_status(
        config_path=args.config,
        survey=survey,
        preflight_check=bool(getattr(args, "preflight", False) and not survey),
    )
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
        pr=getattr(args, "pr", None),
        branch=getattr(args, "branch", None),
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

    t = sub.add_parser("tick", help="Composer: survey + optional live mill pass")
    add_config(t)
    t.add_argument("--live", action="store_true")
    t.set_defaults(func=cmd_tick)

    m = sub.add_parser("mill", help="Composer: tick until idle or max passes")
    add_config(m)
    m.add_argument("--live", action="store_true")
    m.add_argument("--max-passes", type=int, default=8)
    m.set_defaults(func=cmd_mill)

    st = sub.add_parser("status", help="DoD readiness + remaining work (read-only)")
    add_config(st)
    st_mode = st.add_mutually_exclusive_group()
    st_mode.add_argument(
        "--local",
        "--skip-survey",
        action="store_true",
        dest="local",
        help="cheap readiness/config/lease summary (skip multi-repo survey)",
    )
    st_mode.add_argument(
        "--full",
        action="store_true",
        help="full multi-repo remaining-work survey (default)",
    )
    st.add_argument(
        "--preflight",
        action="store_true",
        help="with --local, also run host preflight checks (no lease issue)",
    )
    st.set_defaults(func=cmd_status)

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
    g.add_argument("--pr", type=int)
    g.add_argument("--branch")
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
