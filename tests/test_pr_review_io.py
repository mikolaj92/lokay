from __future__ import annotations

import pytest

from lokay import pr_review_io






class _EvidenceRunner:
    def run_checked(self, spec, *, live):
        from lokay.runner import CommandResult
        import json

        return CommandResult(
            spec=spec,
            executed=live,
            returncode=0,
            stdout=json.dumps({
                "number": 12, "title": "change", "comments": [],
                "headRefName": "ai/fix/12-change", "headRefOid": "b" * 40,
                "baseRefName": "main", "baseRefOid": "a" * 40,
                "url": "https://github.com/mikolaj92/lokay/pull/12",
                "headRepository": {"nameWithOwner": "mikolaj92/lokay"},
            }),
        )

    def run(self, spec, *, live):
        from lokay.runner import CommandResult

        if spec.argv[1:3] == ("api", "graphql"):
            import json
            payload = {"data": {"repository": {"issueOrPullRequest": {
                "__typename": "Issue", "number": 12, "title": "task",
                "body": "body", "state": "OPEN",
                "url": "https://github.com/mikolaj92/lokay/issues/12",
                "repository": {"nameWithOwner": "mikolaj92/lokay"},
            }}}}
            return CommandResult(spec=spec, executed=live, returncode=0, stdout=json.dumps(payload))
        if spec.argv[1:3] == ("pr", "checks"):
            return CommandResult(spec=spec, executed=live, returncode=0, stdout="checks")
        return CommandResult(spec=spec, executed=live, returncode=0, stdout="checks")


def test_pr_review_uses_only_the_exact_local_checkout_patch(monkeypatch) -> None:
    from lokay.config import Config

    class Runner:
        def run_checked(self, spec, *, live):
            from lokay.runner import CommandResult
            return CommandResult(spec, True, 0, stdout='{"number":84,"title":"fix","body":"description","headRefName":"ai/fix/42-x","headRefOid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","baseRefName":"main","baseRefOid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","url":"https://github.com/acme/demo/pull/84","headRepository":{"nameWithOwner":"contributor/demo"},"comments":[]}')
        def run(self, spec, *, live):
            from lokay.runner import CommandResult
            import json
            if spec.argv[1:3] == ("api", "graphql"):
                payload = {"data":{"repository":{"issueOrPullRequest":{"__typename":"Issue","number":42,"title":"task","body":"body","state":"OPEN","url":"https://github.com/acme/demo/issues/42","repository":{"nameWithOwner":"acme/demo"}}}}}
                return CommandResult(spec, True, 0, stdout=json.dumps(payload))
            if spec.argv[1:3] == ("pr", "checks"):
                return CommandResult(spec, True, 0, stdout="green")
            if spec.argv[1:3] == ("pr", "view"):
                return CommandResult(spec, True, 0, stdout=json.dumps({
                    "number":84,"title":"fix","body":"description",
                    "headRefName":"ai/fix/42-x","headRefOid":"b"*40,
                    "baseRefName":"main","baseRefOid":"a"*40,
                    "url":"https://github.com/acme/demo/pull/84",
                    "headRepository":{"nameWithOwner":"contributor/demo"},
                }))
            raise AssertionError(f"unexpected GitHub I/O: {spec.argv}")

    monkeypatch.setattr("lokay.pr_review_io._review_checkout_evidence", lambda *a, **k: {
        "repo_path": "/isolated", "comparison_base_sha": "c"*40,
        "diff_sha256": "d"*64, "diff_paths": [{"path":"x.py","old_path":"","status":"modified"}],
        "changed_ranges": {"x.py": [(1,1)]}, "patch": "exact checkout patch",
    })
    evidence = pr_review_io.load_pr_evidence(Runner(), "acme/demo", 84, live=True,
                                               cfg=Config(), branch="ai/fix/42-x")
    assert evidence["diff"] == "exact checkout patch"


def test_pr_review_does_not_request_a_second_unverified_diff() -> None:
    class ExactRunner(_EvidenceRunner):
        def run(self, spec, *, live):
            if spec.argv[1:3] == ("pr", "diff"):
                raise AssertionError("structured review must not request a second diff")
            if spec.argv[1:3] == ("pr", "checks"):
                from lokay.runner import CommandResult
                return CommandResult(spec, True, 0, stdout="green")
            return super().run(spec, live=live)

    from lokay.config import Config
    import lokay.pr_review_io as io
    original = io._review_checkout_evidence
    io._review_checkout_evidence = lambda *a, **k: {"patch": "exact", "repo_path": "/isolated"}
    try:
        evidence = io.load_pr_evidence(ExactRunner(), "mikolaj92/lokay", 12, live=True, cfg=Config())
        assert evidence["diff"] == "exact"
    finally:
        io._review_checkout_evidence = original


def test_load_pr_evidence_requests_exact_base_and_head_refs_and_preserves_task_candidate(monkeypatch) -> None:
    from lokay.runner import CommandResult

    calls = []

    class Runner:
        def run_checked(self, spec, *, live):
            calls.append(spec.argv)
            return CommandResult(
                spec=spec,
                executed=True,
                returncode=0,
                stdout='{"number":84,"title":"fix","body":"description","headRefName":"ai/fix/42-x","headRefOid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","baseRefName":"main","baseRefOid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","url":"https://github.com/acme/demo/pull/84","headRepository":{"nameWithOwner":"acme/demo"},"comments":[]}',
            )

        def run(self, spec, *, live):
            calls.append(spec.argv)
            if spec.argv[1:3] == ("api", "graphql"):
                import json
                payload = {"data": {"repository": {"issueOrPullRequest": {
                    "__typename": "Issue", "number": 42, "title": "task",
                    "body": "acceptance criteria", "state": "OPEN",
                    "url": "https://github.com/acme/demo/issues/42",
                    "repository": {"nameWithOwner": "acme/demo"},
                }}}}
                return CommandResult(spec=spec, executed=True, returncode=0, stdout=json.dumps(payload))
            return CommandResult(spec=spec, executed=True, returncode=0, stdout="diff --git a/x b/x\\n")

    evidence = pr_review_io.load_pr_evidence(
        Runner(), "acme/demo", 84, live=True,
        branch="ai/fix/42-x", checks_text="green",
    )

    assert evidence["head_sha"] == "b" * 40
    assert evidence["base_ref"] == "main"
    assert evidence["base_ref_sha"] == "a" * 40
    assert evidence["pr"] == 84
    assert evidence["repo"] == "acme/demo"
    assert evidence["task"]["number"] == 42
    assert evidence["task_identity_sha256"]
    assert "baseRefName" in calls[0][-1]
    assert "baseRefOid" in calls[0][-1]
    assert "headRefOid" in calls[0][-1]


def test_revalidation_fails_closed_when_pr_head_changes_during_review(monkeypatch):
    from lokay.pr_review_io import revalidate_pr_identity

    evidence = {
        "repo":"acme/demo", "pr":84, "head_ref":"ai/fix/42-x", "head_sha":"b"*40,
        "base_ref":"main", "base_ref_sha":"a"*40, "head_repo":"contributor/demo",
        "task_identity_sha256":"d"*64,
    }
    view = {
        "number":84,"url":"https://github.com/acme/demo/pull/84",
        "headRefName":"ai/fix/42-x","headRefOid":"e"*40,
        "baseRefName":"main","baseRefOid":"a"*40,
        "headRepository":{"nameWithOwner":"contributor/demo"},
    }
    monkeypatch.setattr("lokay.pr_review_io.gh_json", lambda *_a, **_k: view)
    monkeypatch.setattr("lokay.pr_review_io.resolve_canonical_task", lambda *_a, **_k: {"identity_sha256":"d"*64})
    with pytest.raises(ValueError, match="identity drifted"):
        revalidate_pr_identity(object(), evidence, live=True)


def test_task_identity_prefers_verified_branch_issue_and_rejects_pr_collision():
    from lokay.pr_review_io import resolve_canonical_task

    class GraphQLRunner:
        def __init__(self, typename="Issue", state="OPEN"):
            self.typename = typename
            self.state = state
            self.calls = []

        def run(self, spec, *, live):
            from lokay.runner import CommandResult
            self.calls.append(spec.argv)
            import json
            payload = {
                "data": {
                    "repository": {
                        "issueOrPullRequest": {
                            "__typename": self.typename,
                            "number": 42,
                            "title": "task",
                            "body": "acceptance criteria",
                            "state": self.state,
                            "url": "https://github.com/acme/demo/issues/42",
                            "repository": {"nameWithOwner": "acme/demo"},
                        }
                    }
                }
            }
            return CommandResult(spec, True, 0, stdout=json.dumps(payload))

    good = GraphQLRunner()
    task = resolve_canonical_task(
        good, "acme/demo", pr=84, branch="ai/fix/42-x", branch_prefix="ai/fix", live=True
    )
    assert task["type"] == "Issue" and task["state"] == "OPEN"
    assert task["number"] == 42 and len(task["identity_sha256"]) == 64
    assert good.calls

    collision = GraphQLRunner(typename="PullRequest")
    with pytest.raises(ValueError, match="Issue"):
        resolve_canonical_task(
            collision, "acme/demo", pr=84, branch="ai/fix/42-x", branch_prefix="ai/fix", live=True
        )

    wrong_repo = GraphQLRunner()
    original_run = wrong_repo.run
    def mismatched_repo(spec, *, live):
        result = original_run(spec, live=live)
        from lokay.runner import CommandResult
        return CommandResult(result.spec, True, 0, stdout=result.stdout.replace("acme/demo", "elsewhere/demo"))
    wrong_repo.run = mismatched_repo
    with pytest.raises(ValueError, match="matching OPEN Issue"):
        resolve_canonical_task(
            wrong_repo, "acme/demo", pr=84, branch="ai/fix/42-x", branch_prefix="ai/fix", live=True
        )

    closed = GraphQLRunner(state="CLOSED")
    with pytest.raises(ValueError, match="OPEN"):
        resolve_canonical_task(
            closed, "acme/demo", pr=84, branch="ai/fix/42-x", branch_prefix="ai/fix", live=True
        )


def test_pr_review_source_pins_diff_failure_semantics() -> None:
    from pathlib import Path

    source = Path(pr_review_io.__file__).read_text(encoding="utf-8")
    assert "structured review must use the exact isolated-checkout patch" in source
