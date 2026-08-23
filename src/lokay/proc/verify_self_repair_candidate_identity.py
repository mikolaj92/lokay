"""Purely verify the observed candidate against the requested exact identity."""


def verify(identity: dict) -> dict:
    if identity.get("head") != identity.get("expected_commit"):
        return {
            **identity,
            "ok": False,
            "error": "self-repair candidate changed before validation",
        }
    if identity.get("ahead") != "1" or identity.get("subject") != identity.get(
        "expected_subject"
    ):
        return {
            **identity,
            "ok": False,
            "error": "self-repair candidate commit is not exact",
        }
    return {**identity, "ok": True, "route": "tests"}
