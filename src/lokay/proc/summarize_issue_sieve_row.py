"""Receipt for one sieve row. Never reports an ai/fix launch."""


def summarize(picked: dict, sieve: dict, split: dict, intake: dict) -> dict:
    launched = split.get("launched") or intake.get("launched")
    return {
        "ok": True,
        "result": {
            "repo": picked.get("repo") or sieve.get("repo"),
            "issue": picked.get("issue") or sieve.get("issue"),
            "route": sieve.get("route") or picked.get("route") or "none",
            "reason": sieve.get("reason") or picked.get("reason"),
            "split": split.get("route"),
            "intake": intake.get("route"),
            "launched": None if launched in {None, "", "started"} else launched,
            "leftover": sieve.get("leftover") if sieve.get("leftover") is not None else picked.get("leftover"),
            "leftover_issues": list(
                sieve.get("leftover_issues") or picked.get("leftover_issues") or []
            ),
        },
    }
