"""Thin CLI facade for authored one-PR publication."""

import argparse

from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-create")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", type=int)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file")
    p.add_argument("--body", default="")
    p.add_argument("--head", required=True)
    p.add_argument("--base", default="main")
    args = p.parse_args(argv)
    try:
        from lokay.proc.pr_create_subflow import run

        body = args.body
        if args.body_file:
            from pathlib import Path

            body = Path(args.body_file).read_text(encoding="utf-8")
        out = run(
            config_path=args.config,
            live=bool(args.live),
            repo=args.repo,
            issue=args.issue,
            title=args.title,
            body=body,
            head=args.head,
            base=args.base,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
