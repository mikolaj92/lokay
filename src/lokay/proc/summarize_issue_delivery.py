"""Return the authored issue-delivery terminal envelope."""


def summarize(*, branch: dict, pr_create: dict, pr_label: dict) -> dict:
    pr = pr_create.get("pr") or pr_label.get("pr")
    return {
        "ok": True,
        "result": {
            "branch": branch.get("branch"),
            "pr": pr,
            "delivered": pr not in (None, "", 0),
        },
    }
