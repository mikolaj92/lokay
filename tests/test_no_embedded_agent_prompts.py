from __future__ import annotations

import ast
from pathlib import Path


def test_agent_instructions_are_not_embedded_in_python():
    offenders = []
    for path in Path("src/lokay").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            value = getattr(node, "value", None)
            if not isinstance(value, str) or len(value) < 180:
                continue
            if any(marker in value for marker in ("Rules:", "Return ONLY", "Output ONLY", "Goal:")):
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == []
