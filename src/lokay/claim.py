"""Claim one blueprint run. A stale lease token is a contract failure."""
from lokay.events import Log

MODES = frozenset({"build", "fix_review", "refresh", "review"})


def claim(log, *, resource, token, mode, review_round=0):
    if mode not in MODES or not log.check(resource, token):
        return {"ok": False, "terminal": "contract_failed"}
    return {"ok": True, "mode": mode, "review_round": review_round, "fix_budget": 1}
