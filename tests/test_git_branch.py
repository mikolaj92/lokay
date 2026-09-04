"""Title slugs must not nest git refs (GitHub PR head is one branch)."""

from __future__ import annotations

from lokay.git_branch import branch_for_issue


def _assert_single_head(prefix: str, branch: str) -> None:
    assert branch.startswith(f"{prefix}/")
    assert "/" not in branch[len(prefix) + 1 :]


def test_slash_in_title_is_not_a_nested_ref():
    branch = branch_for_issue(
        "ai/fix",
        "mikolaj92/lokay",
        85,
        "Dodać mikolaj92/heimdall do katalogu Lokaya",
    )
    _assert_single_head("ai/fix", branch)
    assert "mikolaj92-heimdall" in branch
    assert branch.startswith("ai/fix/85-")


def test_docs_path_in_title_is_not_a_nested_ref():
    branch = branch_for_issue(
        "ai/fix",
        "mikolaj92/lokay",
        70,
        "canary lokay smoke add docs/LOKAY_SMOKE.md",
    )
    _assert_single_head("ai/fix", branch)
    assert "canary-lokay-smoke-add-docs-lokay_smoke" in branch


def test_plain_title_keeps_prefix_slash():
    branch = branch_for_issue("ai/fix", "a/b", 3, "Hello World")
    _assert_single_head("ai/fix", branch)
    assert branch.startswith("ai/fix/3-hello-world-")


def test_dotdot_in_title_is_not_a_git_ref():
    # SMT#7-like: SAFE_SLUG treats '.' as legal, so '..' used to survive.
    branch = branch_for_issue(
        "ai/fix",
        "mikolaj92/lokay",
        7,
        "uv.sources pinuje splot na .. splot bez pinowania",
    )
    _assert_single_head("ai/fix", branch)
    assert ".." not in branch
    assert branch.startswith("ai/fix/7-")


def test_triple_dot_in_title_is_not_a_git_ref():
    branch = branch_for_issue("ai/fix", "a/b", 9, "foo...bar")
    _assert_single_head("ai/fix", branch)
    assert ".." not in branch
    assert "foo" in branch and "bar" in branch


def test_smt7_dotdot_slash_title_is_legal_ref():
    # Live SMT#7: unsanitized slug was ai/fix/7-uv.sources-pinuje-splot-na-..-splot-bez-ce23b5da
    title = "uv.sources pinuje splot na ../Splot — bez lokalnego klona import pada"
    branch = branch_for_issue("ai/fix", "mikolaj92/ShowMeThePlayer", 7, title)
    _assert_single_head("ai/fix", branch)
    assert ".." not in branch
    assert branch == "ai/fix/7-uv.sources-pinuje-splot-na-splot-bez-ce23b5da"
