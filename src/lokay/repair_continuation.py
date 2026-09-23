"""Whether a repair head still contains its recorded start SHA."""

from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec


def repair_head_continues(runner: Runner, repo: Path, head: str, recorded: str) -> bool:
    """True when head is the recorded SHA or a descendant of it.

    A prior repair commit stays on the same repair. A foreign line, or a SHA
    git cannot place, is drift.
    """
    if head == recorded:
        return True
    contained = runner.run(
        git_spec(
            ["merge-base", "--is-ancestor", recorded, head],
            cwd=repo, timeout_seconds=30,
        ),
        live=True,
    )
    if contained.returncode == 0 and not (contained.stderr or "").strip():
        return True
    if contained.returncode in (1, 128):
        return False
    raise RuntimeError("cannot verify repair SHA ancestry")
