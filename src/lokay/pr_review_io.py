"""GitHub I/O for structured PR review. Not a review brain."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from lokay.config import Config
from lokay.gh_issues import ensure_labels
from lokay.gh_prs import add_pr_labels, comment_bodies, comment_pr, gh_json, gh_text
from lokay.pr_review import PrReviewDecision, labels_for_review
from lokay.review_style import style_review_comment
from lokay.runner import Runner, gh_spec
from lokay.stuck import issue_number_from_branch

FAIL_CLOSED = (
    "Lokay LLM PR review failed closed (invalid structured output): {exc}\n"
    "Will not auto-merge until a valid review is produced."
)
_VIEW_FIELDS = (
    "number,title,body,headRefName,headRefOid,baseRefName,baseRefOid,"
    "url,isDraft,mergeable,comments,headRepository{nameWithOwner}"
)
_ISSUE_QUERY = """query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){issueOrPullRequest(number:$number){__typename ... on Issue{number title body state url repository{nameWithOwner}} ... on PullRequest{number state url repository{nameWithOwner}}}}}"""
_CLOSING_QUERY = """query($owner:String!,$name:String!,$number:Int!,$after:String){repository(owner:$owner,name:$name){pullRequest(number:$number){closingIssuesReferences(first:100,after:$after){nodes{number} pageInfo{hasNextPage endCursor}}}}}"""
_BRANCH_PREFIX_DEFAULT = "ai/fix"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _repo_parts(repo: str) -> tuple[str, str]:
    parts = repo.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError("invalid GitHub repository identity")
    return parts[0], parts[1]


def _graphql(
    runner: Runner, repo: str, query: str, variables: dict[str, Any], *, live: bool
) -> dict[str, Any]:
    if not live:
        raise ValueError("canonical GitHub issue evidence requires an online read")
    owner, name = _repo_parts(repo)
    args = [
        "api", "graphql", "-f", f"query={query}",
        "-F", f"owner={owner}", "-F", f"name={name}",
    ]
    for key, value in variables.items():
        args.extend(["-F" if isinstance(value, int) else "-f", f"{key}={value}"])
    result = runner.run(gh_spec(args, timeout_seconds=120), live=True)
    if result.returncode != 0:
        raise ValueError("canonical GitHub issue evidence unavailable")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("canonical GitHub issue evidence is malformed") from exc
    if not isinstance(payload, dict) or payload.get("errors"):
        raise ValueError("canonical GitHub issue evidence is incomplete")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("canonical GitHub issue evidence is incomplete")
    return data


def _canonical_issue(runner: Runner, repo: str, number: int, *, live: bool) -> dict[str, Any]:
    owner, name = _repo_parts(repo)
    data = _graphql(
        runner, repo, _ISSUE_QUERY, {"number": number}, live=live
    )
    repository = data.get("repository")
    raw = repository.get("issueOrPullRequest") if isinstance(repository, dict) else None
    if not isinstance(raw, dict) or raw.get("__typename") != "Issue":
        raise ValueError("canonical task must resolve to a GitHub Issue")
    actual_repo = raw.get("repository")
    expected_url = f"https://github.com/{owner}/{name}/issues/{number}"
    if (
        raw.get("number") != number
        or str(raw.get("state") or "").upper() != "OPEN"
        or not isinstance(actual_repo, dict)
        or str(actual_repo.get("nameWithOwner") or "").lower() != repo.lower()
        or raw.get("url") != expected_url
        or not isinstance(raw.get("title"), str)
        or not raw.get("title", "").strip()
        or not isinstance(raw.get("body"), str)
    ):
        raise ValueError("canonical task must be the matching OPEN Issue in the PR repository")
    task = {
        "repo": repo,
        "type": "Issue",
        "state": "OPEN",
        "number": number,
        "title": raw["title"],
        "body": raw["body"],
        "url": expected_url,
    }
    canonical = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**task, "identity_sha256": hashlib.sha256(canonical).hexdigest()}


def _closing_issue_number(runner: Runner, repo: str, pr: int, *, live: bool) -> int:
    after = ""
    seen_cursors: set[str] = set()
    numbers: set[int] = set()
    for _ in range(100):
        data = _graphql(
            runner,
            repo,
            _CLOSING_QUERY,
            {"number": pr, **({"after": after} if after else {})},
            live=live,
        )
        repository = data.get("repository")
        pull = repository.get("pullRequest") if isinstance(repository, dict) else None
        connection = pull.get("closingIssuesReferences") if isinstance(pull, dict) else None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise ValueError("PR closing-issue evidence is incomplete")
        for node in connection["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("number"), int):
                raise ValueError("PR closing-issue evidence is malformed")
            numbers.add(node["number"])
        page = connection.get("pageInfo")
        if not isinstance(page, dict) or not isinstance(page.get("hasNextPage"), bool):
            raise ValueError("PR closing-issue pagination is incomplete")
        if not page["hasNextPage"]:
            break
        cursor = page.get("endCursor")
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            raise ValueError("PR closing-issue pagination did not advance")
        seen_cursors.add(cursor)
        after = cursor
    else:
        raise ValueError("PR closing-issue pagination exceeded its safety bound")
    if len(numbers) != 1:
        raise ValueError("PR must identify exactly one canonical OPEN Issue")
    return next(iter(numbers))


def resolve_canonical_task(
    runner: Runner,
    repo: str,
    *,
    pr: int,
    branch: str,
    branch_prefix: str = "ai/fix",
    live: bool,
) -> dict[str, Any]:
    number = issue_number_from_branch(branch, branch_prefix=branch_prefix)
    if number is None:
        number = _closing_issue_number(runner, repo, pr, live=live)
    return _canonical_issue(runner, repo, number, live=live)


def _verified_pr_view(view: dict[str, Any], repo: str, pr: int, branch: str) -> dict[str, str]:
    if view.get("number") != pr:
        raise ValueError("GitHub PR number does not match requested PR")
    expected_url = f"https://github.com/{repo}/pull/{pr}"
    if view.get("url") != expected_url:
        raise ValueError("GitHub PR repository identity mismatch")
    head_ref = str(view.get("headRefName") or "")
    if not head_ref or (branch and branch != head_ref):
        raise ValueError("GitHub PR head branch changed or does not match selection")
    base_ref = str(view.get("baseRefName") or "")
    head_sha = str(view.get("headRefOid") or "").lower()
    base_sha = str(view.get("baseRefOid") or "").lower()
    if not base_ref or not _SHA_RE.fullmatch(head_sha) or not _SHA_RE.fullmatch(base_sha):
        raise ValueError("GitHub PR base/head refs are incomplete")
    return {
        "head_ref": head_ref,
        "head_sha": head_sha,
        "base_ref": base_ref,
        "base_ref_sha": base_sha,
    }


def _review_checkout_evidence(
    cfg: Config | None, runner: Runner, repo: str, base_sha: str, head_sha: str,
    *, head_repo: str = "",
) -> dict[str, Any]:
    if cfg is None:
        return {}
    from lokay.pr_review_checkout import prepare_review_checkout

    checkout = prepare_review_checkout(
        cfg, runner, repo, base_sha, head_sha, live=True, head_repo=head_repo
    )
    return {
        "repo_path": str(checkout.path),
        "comparison_base_sha": checkout.comparison_base_sha,
        "diff_sha256": checkout.diff_sha256,
        "diff_paths": checkout.diff_paths,
        "changed_ranges": checkout.changed_ranges,
        "patch": checkout.patch.decode("utf-8", errors="replace"),
    }


def revalidate_pr_identity(
    runner: Runner, evidence: dict[str, Any], *, live: bool,
    cfg: Config | None = None, branch_prefix: str = _BRANCH_PREFIX_DEFAULT,
) -> dict[str, Any]:
    """Re-probe the canonical PR and OPEN task around the expensive plugin call."""
    repo, pr = str(evidence.get("repo") or ""), int(evidence.get("pr") or 0)
    view = gh_json(
        runner,
        ["pr", "view", str(pr), "--repo", repo, "--json", _VIEW_FIELDS],
        live=live,
    )
    metadata = _verified_pr_view(view, repo, pr, str(evidence.get("head_ref") or ""))
    if view.get("isDraft") is True:
        raise ValueError("draft PR cannot enter structured review and merge flow")
    head_repository = view.get("headRepository")
    head_repo = str(head_repository.get("nameWithOwner") or "") if isinstance(head_repository, dict) else ""
    task = resolve_canonical_task(
        runner, repo, pr=pr, branch=metadata["head_ref"],
        branch_prefix=branch_prefix, live=live,
    )
    if (
        metadata["head_sha"] != evidence.get("head_sha")
        or metadata["base_ref_sha"] != evidence.get("base_ref_sha")
        or metadata["base_ref"] != evidence.get("base_ref")
        or head_repo != evidence.get("head_repo")
        or task["identity_sha256"] != evidence.get("task_identity_sha256")
    ):
        raise ValueError("PR or canonical task identity drifted during review")
    if cfg is not None:
        from lokay.pr_review_checkout import recompute_review_evidence
        from lokay.pr_review_checkout import ReviewCheckout

        checkout = ReviewCheckout(
            path=Path(str(evidence["repo_path"])),
            comparison_base_sha=str(evidence["comparison_base_sha"]),
            diff_sha256=str(evidence["diff_sha256"]),
            diff_paths=list(evidence["diff_paths"]),
            changed_ranges=dict(evidence["changed_ranges"]),
            patch=b"",  # recomputation reads canonical patch bytes from the pinned checkout
        )
        recompute_review_evidence(
            runner, checkout, base_ref_sha=metadata["base_ref_sha"], head_sha=metadata["head_sha"]
        )
    if cfg is None:
        raise ValueError("live checkout evidence is required to revalidate a PR review")
    prefix = branch_prefix.strip("/")
    issue_branch = issue_number_from_branch(metadata["head_ref"], branch_prefix=prefix)
    if issue_branch is None:
        closing_number = _closing_issue_number(runner, repo, pr, live=live)
        if closing_number != int(task["number"]):
            raise ValueError("canonical PR closing issue changed during review")
    return {
        "repo": repo, "pr": pr, "head_ref": metadata["head_ref"], "head_repo": head_repo,
        "head_sha": metadata["head_sha"], "base_ref": metadata["base_ref"],
        "base_ref_sha": metadata["base_ref_sha"],
        "task_identity_sha256": task["identity_sha256"],
        "comparison_base_sha": str(evidence.get("comparison_base_sha") or ""),
        "diff_sha256": str(evidence.get("diff_sha256") or ""),
        "diff_paths": list(evidence.get("diff_paths") or []),
        "changed_ranges": dict(evidence.get("changed_ranges") or {}),
    }


def load_pr_evidence(
    runner: Runner,
    repo: str,
    pr: int,
    *,
    live: bool,
    cfg: Config | None = None,
    branch: str = "",
    branch_prefix: str = "ai/fix",
    checks_text: str = "",
) -> dict[str, Any]:
    view = gh_json(
        runner,
        ["pr", "view", str(pr), "--repo", repo, "--json", _VIEW_FIELDS],
        live=live,
    )
    if not live:
        return {
            "title": "", "body": "", "head": branch, "head_ref": branch,
            "head_sha": "", "base_ref": "", "base_ref_sha": "", "head_repo": "",
            "repo": repo, "pr": pr, "task": {}, "task_identity_sha256": "",
            "comments": [], "diff": "", "checks_text": checks_text,
        }
    metadata = _verified_pr_view(view, repo, pr, branch)
    if view.get("isDraft") is True:
        raise ValueError("draft PR cannot enter structured review and merge flow")
    task = resolve_canonical_task(
        runner, repo, pr=pr, branch=metadata["head_ref"],
        branch_prefix=branch_prefix, live=True,
    )
    head_repository = view.get("headRepository")
    head_repo = str(head_repository.get("nameWithOwner") or "") if isinstance(head_repository, dict) else ""
    if not head_repo or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repo):
        raise ValueError("GitHub PR head repository identity is missing or malformed")
    checkout_evidence = _review_checkout_evidence(
        cfg, runner, repo, metadata["base_ref_sha"], metadata["head_sha"],
        head_repo=head_repo,
    )
    checkout_evidence["head_repo"] = head_repo
    # structured review must use the exact isolated-checkout patch; do not ask gh for a second diff.
    diff = str(checkout_evidence.get("patch") or "")
    if cfg is not None and not diff:
        raise ValueError("exact isolated checkout patch is missing")
    if not checks_text and live:
        checks_text = gh_text(
            runner, ["pr", "checks", str(pr), "--repo", repo], live=live
        )
    return {
        "repo": repo,
        "pr": pr,
        "title": str(view.get("title") or ""),
        "body": str(view.get("body") or ""),
        "head": metadata["head_ref"],
        **metadata,
        "task": {key: value for key, value in task.items() if key != "identity_sha256"},
        "task_identity_sha256": task["identity_sha256"],
        "comments": comment_bodies(view),
        "diff": diff,
        "checks_text": checks_text,
        **checkout_evidence,
    }


def review_worktree(cfg: Config, repo: str) -> Path | None:
    """Return the review directory, or skip repos outside this mini lokay."""
    try:
        worktree = next(r.clone_path for r in cfg.repos if r.name == repo)
        if not worktree.is_dir():
            raise KeyError(repo)
    except Exception:
        worktree = Path(tempfile.mkdtemp(prefix="lokay-pr-review-"))
    return worktree


def publish_review(
    runner: Runner,
    repo: str,
    pr: int,
    body: str,
    labels: list[str],
    *,
    live: bool,
) -> None:
    comment_pr(runner, repo, pr, body, live=live)
    if labels:
        ensure_labels(runner, repo, labels, live=live)
        add_pr_labels(runner, repo, pr, labels, live=live)


def publish_fail_closed(
    runner: Runner, repo: str, pr: int, exc: Exception, *, mutate: bool
) -> bool:
    if not mutate:
        return False
    try:
        publish_review(
            runner, repo, pr, FAIL_CLOSED.format(exc=exc), ["ai:needs-review"], live=True
        )
        return True
    except Exception:
        return False


def publish_decision(
    runner: Runner,
    repo: str,
    pr: int,
    decision: PrReviewDecision,
    *,
    head_sha: str,
    merge_ok: bool,
    escalated: bool,
    mutate: bool,
    style_target: str = "",
) -> None:
    if not mutate:
        return
    publish_review(
        runner,
        repo,
        pr,
        style_review_comment(
            decision,
            head_sha=head_sha,
            merge_ok=merge_ok,
            escalated=escalated,
            target=style_target,
        ),
        labels_for_review(decision, escalated=escalated),
        live=True,
    )
