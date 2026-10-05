"""README carries a generated Fala path index; the checker compares, never scrapes."""

import tomllib
from pathlib import Path

from lokay.readme_state_machine import (
    BEGIN_MARKER,
    END_MARKER,
    verify_readme_sync,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "fala" / "lokay.fala-package.toml"
README = ROOT / "README.md"
FALA_PATHS_DOC = ROOT / "docs" / "FALA_PATHS.md"


def _authored_ids() -> set[str]:
    package = tomllib.loads(PACKAGE.read_text(encoding="utf-8"))
    return {str(path["id"]) for path in package["correlation_paths"]}


def test_readme_path_index_is_synchronized():
    ok, errors = verify_readme_sync(package_path=PACKAGE, readme_path=README)
    assert ok, f"README sync failed: {errors}"


def test_readme_index_covers_every_authored_path():
    readme = README.read_text(encoding="utf-8")
    start = readme.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = readme.index(END_MARKER)
    section = readme[start:end]
    for path_id in _authored_ids():
        assert f"`{path_id}`" in section, path_id


def test_readme_sync_fails_on_stale_section(tmp_path):
    readme = README.read_text(encoding="utf-8")
    begin = readme.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = readme.index(END_MARKER)
    stale = readme[:begin] + "\n| `ghost_path` | Ghost |\n" + readme[end:]
    stale_file = tmp_path / "README.md"
    stale_file.write_text(stale, encoding="utf-8")
    ok, errors = verify_readme_sync(package_path=PACKAGE, readme_path=stale_file)
    assert not ok
    assert any("stale" in error for error in errors)


def test_readme_sync_fails_without_markers(tmp_path):
    readme_file = tmp_path / "README.md"
    readme_file.write_text("# Lokay\n", encoding="utf-8")
    ok, errors = verify_readme_sync(package_path=PACKAGE, readme_path=readme_file)
    assert not ok
    assert any("marker" in error.lower() for error in errors)


def test_checker_does_not_scrape_prose_with_regex():
    source = (ROOT / "src" / "lokay" / "readme_state_machine.py").read_text(encoding="utf-8")
    assert "import re" not in source
    assert "re.findall" not in source
    assert "re.compile" not in source


def test_readme_state_machine_invariants_stay_in_readme():
    readme = README.read_text(encoding="utf-8")
    assert "```mermaid\nstateDiagram-v2" in readme
    assert "Każda zmiana przepływu zaczyna się" in readme
    assert "Lokay nie używa GitHub Actions" in readme
    assert "pr_metadata" in readme
    assert "fail-closed, bez generatywnego retry" in readme


def test_moved_contract_keeps_agent_feedback_phrases():
    doc = FALA_PATHS_DOC.read_text(encoding="utf-8")
    assert "invalid JSON + informacja zwrotna" in doc
    assert "NEEDS_EVIDENCE" in doc


def test_per_path_diagrams_moved_out_of_readme():
    readme = README.read_text(encoding="utf-8")
    assert "### Zamknięcie PR — `pr_triage`" not in readme
    assert "### Otwarcie workspace passu — `factory_begin`" not in readme


def test_review_loop_diagram_contract_lives_in_docs():
    doc = FALA_PATHS_DOC.read_text(encoding="utf-8")
    start = doc.index("### Zamknięcie PR — `pr_triage`")
    end = doc.index("### Naprawa istniejącego PR — `pr_repair`", start)
    graph = doc[start:end]

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
    assert "LocalMergeGate --> PrepareDeliveryCloseout" in graph
    assert "PrepareDeliveryCloseout --> MergePullRequest" in graph


def test_repository_has_no_github_actions_workflows():
    workflows = ROOT / ".github" / "workflows"
    assert not workflows.exists() or not any(workflows.iterdir())
