"""Select exact PR review scope through the isolated engine's preview operation."""
from __future__ import annotations

import argparse
import copy
import json
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.proc.pr_review_plugin import PluginFailure, invoke_plugin


def select(*, config_path: str | None, repo: str, pr: int, evidence: dict[str, Any], live: bool) -> dict[str, Any]:
    if not live:
        return ok(route="planned")
    from lokay.config import load_config
    from lokay.proc.run_pr_review_agent import plugin_request
    try:
        cfg = load_config(config_path)
        request = plugin_request(cfg, repo, pr, evidence)
        scoped = copy.copy(cfg)
        scoped.pr_review_plugin_args = [*cfg.pr_review_plugin_args, "--operation", "scope"]
        result = invoke_plugin(scoped, request)
        identities = ("repo", "pr", "head_sha", "base_ref_sha", "comparison_base_sha",
                      "diff_sha256", "task_identity_sha256", "review_config_sha256")
        if (result.get("schema") != "lokay.review-scope/1"
                or any(result.get(key) != request.get(key) for key in identities)
                or not isinstance(result.get("preview"), dict)):
            raise PluginFailure("ocr_scope_identity_mismatch")
        return ok(route="ready", scope=result)
    except (PluginFailure, ValueError, OSError) as exc:
        # Classified success at the process layer lets Fala reach its fail-closed terminal.
        return ok(route="fail_closed", reason="ocr_scope_incomplete", detail=str(exc))


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
