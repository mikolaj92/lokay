"""Validate the requested exact self-repair identity fields."""


def validate(state: dict, *, expected_subject: str, expected_commit: str) -> dict:
    if not expected_subject:
        return {
            **state,
            "ok": True,
            "route": "tests",
            "expected_subject": "",
            "expected_commit": "",
        }
    if not state.get("base_sha"):
        return {**state, "ok": False, "error": "self-repair candidate base is required"}
    if len(expected_commit) != 40 or any(
        x not in "0123456789abcdef" for x in expected_commit
    ):
        return {**state, "ok": False, "error": "self-repair expected commit is invalid"}
    if state.get("changed"):
        return {
            **state,
            "ok": False,
            "error": "self-repair candidate has uncommitted changes",
        }
    return {
        **state,
        "ok": True,
        "route": "inspect",
        "expected_subject": expected_subject,
        "expected_commit": expected_commit,
    }
