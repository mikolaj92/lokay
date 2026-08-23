"""Verify that supplemental PR evidence still belongs to the reviewed SHA."""
from __future__ import annotations
from lokay.envelope import ok
from lokay.gh_prs import gh_json
from lokay.proc._common import runner

def verify(*, repo: str, pr: int, expected_sha: str, live: bool) -> dict:
    try:
        view=gh_json(runner(),["pr","view",str(pr),"--repo",repo,"--json","headRefOid"],live=live)
    except Exception as exc:
        return ok(route="needs_human",reason=f"failed to verify supplemental evidence SHA: {exc}",probe_failed=True)
    actual=str(view.get("headRefOid") or "").strip().lower()
    expected=str(expected_sha or "").strip().lower()
    if live and (not expected or actual != expected):
        return ok(route="needs_human",reason="supplemental review evidence SHA changed",expected_sha=expected,actual_sha=actual)
    return ok(route="agent",repo=repo,pr=pr,head_sha=actual or expected)


def main(argv=None):
    import argparse
    from lokay.envelope import emit_exit
    from lokay.proc._common import add_config_read
    parser=argparse.ArgumentParser(prog="lokay-verify-review-evidence-sha"); add_config_read(parser)
    parser.add_argument("--repo",required=True); parser.add_argument("--pr",required=True,type=int); parser.add_argument("--expected-sha",required=True)
    args=parser.parse_args(argv)
    return emit_exit(verify(repo=args.repo,pr=args.pr,expected_sha=args.expected_sha,live=not args.offline))
if __name__ == "__main__": raise SystemExit(main())
