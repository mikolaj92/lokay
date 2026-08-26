"""Record the NIE sito outcome. Do not implement."""


def apply(*, decision: dict) -> dict:
    return {
        "ok": True,
        "applied": False,
        "skipped": True,
        "verdict": "skip",
        "reason": str(decision.get("reason") or "skip"),
    }
