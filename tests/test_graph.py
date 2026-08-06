from pathlib import Path

from lokay.graph_run import describe_package


def test_describe_issue_to_pr_graph():
    desc = describe_package()
    assert desc["package_id"] == "lokay"
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    ids = [n["id"] for n in path["nodes"]]
    assert ids[0] == "get_issue"
    assert "run_agent" in ids
    assert "pr_create" in ids
    # agent depends on worktree
    agent = next(n for n in path["nodes"] if n["id"] == "run_agent")
    assert "worktree_add" in agent["conduction"]
    assert "get_issue" in agent["conduction"]


def test_package_file_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "fala" / "lokay.fala-package.toml").is_file()
