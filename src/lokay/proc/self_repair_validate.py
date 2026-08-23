"""CLI facade for authored self-repair candidate validation."""

import argparse
from lokay.envelope import emit_exit, err


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-self-repair-validate")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--expected-subject", default="")
    parser.add_argument("--expected-commit", default="")
    args = parser.parse_args(argv)
    try:
        from lokay.proc.self_repair_validate_subflow import run

        out = run(
            worktree=args.worktree,
            base_sha=args.base_sha,
            expected_subject=args.expected_subject,
            expected_commit=args.expected_commit,
        )
    except Exception as exc:
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
