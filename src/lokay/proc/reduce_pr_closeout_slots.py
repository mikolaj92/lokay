"""Reduce authored closeout slot records into pass state."""

from lokay.passkit.working import load_begin_working
from lokay.proc.reduce_pr_closeout import reduce_state


def reduce(*, prepared: dict, rows: list[dict], pass_dir: str) -> dict:
    if not prepared.get("ok"):
        return dict(prepared)
    _, working = load_begin_working(pass_dir)
    present = [row for row in rows if isinstance(row, dict) and row]
    return reduce_state(prepared=prepared, rows=present, working=working)
