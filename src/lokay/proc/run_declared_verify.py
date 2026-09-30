"""Turn a declared verify command into product proof.

The command itself is the declared argv. This atom only closes the verdict:
green after a real declaration is verified, anything else is not.
"""


def run(inspected: dict, executed: dict) -> dict:
    if inspected.get("route") != "verify":
        result = dict(inspected.get("result") or {})
        return {
            "ok": result.get("ok", True) is not False,
            "verified": False,
            "skipped": bool(result.get("skipped")),
            "reason": str(result.get("reason") or "no_declared_verify"),
            "worktree": str(result.get("worktree") or inspected.get("worktree") or ""),
        }
    if executed.get("route") == "green" and executed.get("returncode") == 0:
        return {
            "ok": True,
            "verified": True,
            "skipped": False,
            "worktree": str(inspected.get("worktree") or ""),
            "verify": str(executed.get("tests") or " ".join(inspected.get("verify_argv") or [])),
        }
    return {
        "ok": False,
        "verified": False,
        "skipped": False,
        "error": str(executed.get("error") or "declared verify command failed"),
        "returncode": executed.get("returncode"),
        "worktree": str(inspected.get("worktree") or ""),
        "verify": str(executed.get("tests") or " ".join(inspected.get("verify_argv") or [])),
        "stdout_tail": executed.get("stdout_tail", ""),
        "stderr_tail": executed.get("stderr_tail", ""),
    }
