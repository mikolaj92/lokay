"""Thin CLI facade for authored one-issue stage transition."""

import argparse

from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live
from lokay.stage_ledger import STAGES


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-stage-label")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--stage", required=True, choices=sorted(STAGES))
    p.add_argument("--receipt", action="store_true")
    p.add_argument("--comment", default="")
    args = p.parse_args(argv)
    try:
        from lokay.proc.stage_label_subflow import run

        out = run(
            config_path=args.config,
            live=bool(args.live),
            repo=args.repo,
            issue=args.issue,
            stage=args.stage,
            receipt=args.receipt,
            comment=args.comment,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
