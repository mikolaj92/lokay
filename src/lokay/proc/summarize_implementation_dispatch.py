"""Return the authored terminal result of one implementation dispatch subflow."""

from lokay.passkit import io as pass_io


def summarize(*, pass_dir: str) -> dict:
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    started = int(working.get("issue_to_pr_started") or 0)
    return {
        "ok": True,
        "result": {"pass_dir": pass_dir, "started": started, "detached": started > 0},
    }
