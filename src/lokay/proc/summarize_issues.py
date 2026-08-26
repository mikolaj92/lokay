"""Receipt for one issues pass. Two small functions: envelope, then write."""

from lokay.proc.write_issues_receipt import write


def envelope(picked: dict, do: dict, launched: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "issue": picked.get("issue"),
            "repo": picked.get("repo"),
            "route": str(do.get("route") or picked.get("route") or "none"),
            "reason": do.get("reason") or picked.get("reason"),
            "launched": launched.get("route"),
        },
    }


def summarize(
    picked: dict,
    do: dict,
    launched: dict,
    *,
    pass_dir: str = "",
) -> dict:
    return write(envelope(picked, do, launched), pass_dir=pass_dir)
