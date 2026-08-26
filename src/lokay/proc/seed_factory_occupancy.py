"""Copy live issue_to_pr occupancy into working. One job."""

from lokay.proc.seed_prior_catalog import seed


def run(working: dict) -> dict:
    inner = dict(working.get("working") or working)
    return {
        "ok": True,
        "working": seed(working=inner, begin={}, pass_dir=""),
    }
