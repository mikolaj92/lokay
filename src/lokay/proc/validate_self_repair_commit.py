"""Validate exact fingerprint commit count, subject, and real paths."""


def validate(commit: dict) -> dict:
    if (
        int(commit.get("ahead") or 0) != 1
        or commit.get("subject") != f"self-repair: {commit['fingerprint']}"
    ):
        return {
            **commit,
            "route": "error",
            "error": "cannot resume unrecognized committed self-repair candidate",
        }
    if commit.get("committed") != "real":
        return {
            **commit,
            "route": "error",
            "error": "cannot resume self-repair worktree with committed plan evidence",
        }
    return {**commit, "route": "ancestry"}
