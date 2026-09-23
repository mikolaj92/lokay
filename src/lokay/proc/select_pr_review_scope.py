"""Select exact PR review scope through the isolated engine's preview operation."""
from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.envelope import emit_exit, err, ok


def select(*, config_path: str | None, repo: str, pr: int, evidence: dict[str, Any], live: bool) -> dict[str, Any]:
    del config_path, repo, pr
    if not live:
        return ok(route="planned")
    paths = evidence.get("diff_paths")
    if not isinstance(paths, list) or not paths:
        return ok(route="fail_closed", reason="ocr_scope_incomplete")
    return ok(route="ready", scope={"diff_paths": list(paths)})


def main(argv=None):
    from lokay.proc._common import add_config_live
    parser = argparse.ArgumentParser(prog="lokay-select-pr-review-scope")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence_json)
    except json.JSONDecodeError:
        return emit_exit(err("invalid review scope input"))
    if not isinstance(evidence, dict):
        return emit_exit(err("review scope input object required"))
    return emit_exit(select(config_path=args.config, repo=args.repo, pr=args.pr,
                            evidence=evidence, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
