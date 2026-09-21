"""The reviewed README state machine names every authored Fala path."""

import tomllib
from pathlib import Path

from lokay.readme_state_machine import verify_readme_sync

ROOT = Path(__file__).resolve().parents[1]


def test_readme_contains_mermaid_state_machine_before_implementation_contract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "```mermaid\\nstateDiagram-v2" in readme or "```mermaid\nstateDiagram-v2" in readme
    assert "Każda zmiana przepływu zaczyna się" in readme
    assert "Lokay nie używa GitHub Actions" in readme
    assert "invalid JSON + informacja zwrotna" in readme
    assert "NEEDS_EVIDENCE" in readme
    assert "pr_metadata" in readme
    assert "fail-closed, bez generatywnego retry" in readme


def test_readme_state_machine_maps_every_fala_path():
    ok, errors = verify_readme_sync(
        package_path=ROOT / "fala" / "lokay.fala-package.toml",
        readme_path=ROOT / "README.md",
    )
    assert ok, f"README sync failed: {errors}"


def test_pr_review_diagram_captures_opencode_review_and_parent_repair_loop():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("### Zamknięcie PR — `pr_triage`")
    end = readme.index("### Naprawa istniejącego PR — `pr_repair`", start)
    graph = readme[start:end]

    assert "ResolveShaReview --> SelectPrReviewScope" in graph
    assert "SelectPrReviewScope --> OpenCodeReview" in graph
    assert "SelectPrReviewScope --> HumanTerminal" in graph
    assert "OpenCodeReview --> ValidateReviewResult" in graph
    assert "ocr review" in graph
    assert "OpenCodeReviewPlugin" not in graph
    assert "no retry" in graph
    assert "ValidateReviewResult --> HumanTerminal" in graph
    assert "ReviewVerdict --> RepairVerdict: REQUEST_CHANGES" in graph
    assert "RepairVerdict --> TriageReceipt: task + wszystkie findings" in graph
    assert "TriageReceipt --> FactoryParentRepairSelect" in graph
    assert "FactoryParentRepairSelect --> RepairPullRequest" in graph
    assert "TriageReceipt --> RevalidateCanonicalTask" in graph
    assert "RevalidateCanonicalTask --> RepairPullRequest" in graph
    assert "RevalidateCanonicalTask --> HumanTerminal" in graph
    assert "RepairPullRequest --> VerifyRepairStartHead" in graph
    assert "VerifyRepairStartHead --> RepairPullRequest" in graph
    assert "VerifyRepairStartHead --> HumanTerminal" in graph
    assert "PR z forka" in graph
    assert "RepairPullRequest --> NewHeadSha" in graph
    assert "NewHeadSha --> NextFactoryPassReview" in graph
    assert "ReviewVerdict --> LocalMergeGate: APPROVE" in graph
    assert "LocalMergeGate --> MergePullRequest" in graph


def test_repository_has_no_github_actions_workflows():
    workflows = ROOT / ".github" / "workflows"
    assert not workflows.exists() or not any(workflows.iterdir())


def test_flow_headings_use_authored_fala_path_ids():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    package = tomllib.loads(
        (ROOT / "fala" / "lokay.fala-package.toml").read_text(encoding="utf-8")
    )
    authored = {str(path["id"]) for path in package["correlation_paths"]}
    import re
    headings = dict(
        re.findall(r"^### ([^\n]+?) — `([a-z0-9_]+)`$", readme, re.MULTILINE)
    )
    for title in (
        "Uruchomienie triage",
        "Uruchomienie implementacji",
        "Higiena worktree",
    ):
        assert headings[title] in authored
