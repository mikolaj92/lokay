"""Read whether one over-budget wrapper still has a coder descendant."""

from lokay.proc.detach_issue_to_pr import wrapper_has_coding_descendant


def inspect(budget: dict) -> dict:
    live = wrapper_has_coding_descendant(int(budget["pid"]))
    return {**budget, "route": "diff" if live else "reap", "coder_live": live}
