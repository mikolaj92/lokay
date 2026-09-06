"""Semantic bindings must be named contracts, never hidden mechanical agents."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_real_agent_bindings_are_documented_contracts():
    bindings = set()
    for source in (ROOT / "src/lokay/organ").glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            if not isinstance(node.test.left, ast.Name) or node.test.left.id != "atom":
                continue
            body = ast.Module(body=node.body, type_ignores=[])
            invokes_agent = any(
                isinstance(n, ast.ImportFrom)
                and n.module and n.module.startswith("lokay.proc.run_")
                and "agent" in n.module
                for n in ast.walk(body)
            ) or any(
                isinstance(n, ast.Call)
                and any(isinstance(arg, ast.Attribute) and ast.unparse(arg) == "run_agent.main" for arg in n.args)
                for n in ast.walk(body)
            )
            if invokes_agent:
                bindings.update(n.value for n in ast.walk(node.test.comparators[0]) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    document = (ROOT / "docs/PROCESS.md").read_text()
    documented = set()
    for line in document.splitlines():
        if line.startswith("| `") and " | entropy | " in line:
            documented.add(line.split("`", 2)[1])
    assert bindings == documented
    assert not bindings.intersection({"pr_merge", "host_ff", "list_prs", "resolve_issue_hard_facts"})
