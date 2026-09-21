"""Fail-closed parsing and Git errors for repair's exact evidence allowance."""
from pathlib import Path

import pytest

from lokay.repair_worktree_dirt import repair_worktree_dirt
from lokay.runner import CommandResult


@pytest.mark.parametrize(("responses", "expected"), [
    ([(0, "", "")], "clean"),
    ([(1, "", "")], "unavailable"),
    ([(0, "", "warning")], "unavailable"),
    ([(0, " M .lokay/approach.md", "")], "unavailable"),
    ([(0, " M .lokay/approach.md\0", ""), (1, "", "")], "unavailable"),
    ([(0, " M .lokay/approach.md\0", ""), (0, "bad\0", "")], "unavailable"),
    ([(0, "UU .lokay/approach.md\0", "")], "product"),
    ([(0, "R  .lokay/approach.md\0product.py\0", "")], "product"),
    ([(0, "?? .lokay/approach.md\0", ""), (0, "", ""), (0, "", "")], "evidence"),
    ([(0, " D .lokay/approach.md\0", ""), (0, "", ""),
      (0, "120000 blob abc\t.lokay/approach.md\0", "")], "product"),
])
def test_status_classification(tmp_path: Path, responses, expected):
    pending = iter(responses)

    class Runner:
        def run(self, spec, *, live):
            code, stdout, stderr = next(pending)
            return CommandResult(spec, live, code, stdout, stderr)

    assert repair_worktree_dirt(Runner(), tmp_path) == expected
    assert list(pending) == []
