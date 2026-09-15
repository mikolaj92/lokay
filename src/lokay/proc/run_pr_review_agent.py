"""Run one initial OpenCodeReview plugin invocation over exact PR evidence."""

from __future__ import annotations

from typing import Any

from lokay.config import Config, load_config
from lokay.envelope import err, ok
from lokay.proc.pr_review_plugin import PluginFailure, invoke_plugin


def plugin_request(cfg: Config, repo: str, pr: int, evidence: dict[str, Any]) -> dict[str, Any]:
    task = evidence.get("task")
    if not isinstance(task, dict):
        raise PluginFailure("canonical task evidence is required")
    request = {
        "schema": "lokay.review-request/1",
        "repo": repo,
        "pr": pr,
        "head_ref": str(evidence.get("head_ref") or ""),
        "head_repo": str(evidence.get("head_repo") or ""),
        "head_sha": str(evidence.get("head_sha") or ""),
        "base_ref": str(evidence.get("base_ref") or ""),
        "base_ref_sha": str(evidence.get("base_ref_sha") or ""),
        "comparison_base_sha": str(evidence.get("comparison_base_sha") or ""),
        "repo_path": str(evidence.get("repo_path") or ""),
        "diff_paths": evidence.get("diff_paths") or [],
        "diff_sha256": str(evidence.get("diff_sha256") or ""),
        "changed_ranges": evidence.get("changed_ranges") or {},
        "pr_title": str(evidence.get("title") or ""),
        "pr_body": str(evidence.get("body") or ""),
        "task": task,
        "task_identity_sha256": str(evidence.get("task_identity_sha256") or ""),
        "review_config_sha256": cfg.pr_review_config_sha256,
        "engine": {
            "name": "open-code-review",
            "version": cfg.pr_review_binary_version,
            "binary_path": str(cfg.pr_review_binary or ""),
            "binary_sha256": cfg.pr_review_binary_sha256,
            "provider": cfg.pr_review_provider,
            "provider_endpoint_url": cfg.pr_review_provider_endpoint_url,
            "model": cfg.pr_review_model,
            "effort": cfg.pr_review_effort,
            "timeout_minutes": cfg.pr_review_timeout_minutes,
            "max_tokens_budget": cfg.pr_review_max_tokens_budget,
            "config_sha256": cfg.pr_review_config_sha256,
            "rule_path": str(cfg.pr_review_rule_file or ""),
            "tools_path": str(cfg.pr_review_tools_file or ""),
            "ocr_config_path": str(cfg.pr_review_ocr_config or ""),
            "sandbox_command": list(cfg.pr_review_sandbox_command),
            "sandbox_profile_path": str(cfg.pr_review_sandbox_profile or ""),
            "env_allowlist": list(cfg.pr_review_provider_env),
        },
    }
    return request


def run_review_agent(
    *,
    config_path: str | None,
    repo: str,
    pr: int,
    evidence: dict[str, Any],
    live: bool,
) -> dict[str, Any]:
    if not live:
        return {"ok": True, "route": "planned", "stdout": "", "result": {}}
    try:
        cfg = load_config(config_path)
        request = plugin_request(cfg, repo, pr, evidence)
        from lokay.proc._common import runner as make_runner
        from lokay.pr_review_io import revalidate_pr_identity

        gh_runner = make_runner(cfg)
        before = revalidate_pr_identity(
            gh_runner, evidence, live=live, cfg=cfg, branch_prefix=cfg.branch_prefix
        )
        result = invoke_plugin(cfg, request)
        after = revalidate_pr_identity(
            gh_runner, evidence, live=live, cfg=cfg, branch_prefix=cfg.branch_prefix
        )
        if before != after or any(
            after.get(key) != evidence.get(key)
            for key in (
                "repo", "pr", "head_ref", "head_repo", "head_sha", "base_ref",
                "base_ref_sha", "comparison_base_sha", "diff_sha256",
                "task_identity_sha256", "diff_paths", "changed_ranges",
            )
        ):
            raise PluginFailure("PR identity or exact diff drifted during review")
        if (
            result.get("repo") != repo
            or result.get("pr") != pr
            or result.get("head_sha") != evidence.get("head_sha")
            or result.get("base_ref_sha") != evidence.get("base_ref_sha")
            or result.get("comparison_base_sha") != evidence.get("comparison_base_sha")
            or result.get("diff_sha256") != evidence.get("diff_sha256")
            or result.get("task_identity_sha256") != evidence.get("task_identity_sha256")
            or result.get("head_repo") != evidence.get("head_repo")
            or result.get("head_ref") != evidence.get("head_ref")
            or result.get("base_ref") != evidence.get("base_ref")
        ):
            raise PluginFailure("review plugin result identity does not match request")
        execution = dict(result.get("evidence") or {}).get("upstream_execution") or {}
        result["review_execution"] = {
            "preview_sha256": str((result.get("evidence") or {}).get("preview_sha256") or ""),
            "input_fingerprint_sha256": str((result.get("evidence") or {}).get("input_fingerprint_sha256") or ""),
            "rule_config_sha256": str(execution.get("rule_config_sha256") or ""),
            "runtime_config_sha256": str(execution.get("runtime_config_sha256") or ""),
        }
        return ok(
            repo=repo,
            pr=pr,
            head_sha=str(evidence.get("head_sha") or ""),
            stdout=__import__("json").dumps(result, ensure_ascii=False, separators=(",", ":")),
            result=result,
            request=request,
            route="complete",
        )
    except (PluginFailure, OSError, ValueError) as exc:
        return err("OpenCodeReview plugin failed closed", route="fail_closed", reason=str(exc))


def main(argv=None):
    import argparse
    import json

    from lokay.envelope import emit_exit
    from lokay.proc._common import add_config_live

    parser = argparse.ArgumentParser(prog="lokay-run-pr-review-agent")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid PR review input JSON: {exc}"))
    if not isinstance(evidence, dict):
        return emit_exit(err("PR review evidence object required"))
    return emit_exit(
        run_review_agent(
            config_path=args.config,
            repo=args.repo,
            pr=args.pr,
            evidence=evidence,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
