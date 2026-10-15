from collections.abc import Callable

from lokay import graph, store
from lokay.types import Event, Run


def tick(repo: str, issue: int, act: Callable[[Run], Event]) -> Run:
    run = store.load(repo, issue)
    event = act(run)
    run = graph.step(run, event)
    store.save(repo, issue, run, event)
    return run
