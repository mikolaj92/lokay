"""Compatibility slot; structured review errors do not trigger an agent retry."""

from __future__ import annotations


def run(*, config_path: str | None, repo: str, pr: int, evidence: dict, feedback: dict, live: bool) -> dict:
    del config_path, repo, pr, evidence, feedback, live
    return {"ok": True, "route": "not_applicable", "stdout": ""}


def main(argv=None):
    import argparse
    import json

    from lokay.envelope import emit_exit, err
    from lokay.proc._common import add_config_live

    parser = argparse.ArgumentParser(prog="lokay-run-pr-review-retry-agent")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--evidence-json", required=True)
    parser.add_argument("--feedback-json", required=True)
    args = parser.parse_args(argv)
    try:
        evidence, feedback = json.loads(args.evidence_json), json.loads(args.feedback_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid retry input JSON: {exc}"))
    return emit_exit(run(config_path=args.config, repo=args.repo, pr=args.pr,
                         evidence=evidence, feedback=feedback, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
