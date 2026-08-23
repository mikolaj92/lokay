"""Fala-only composition for issue → PR."""

from __future__ import annotations
import argparse, os
from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.state import append_event


def _await_detach_activation() -> bool:
    raw = os.environ.get("LOKAY_ISSUE_TO_PR_ACTIVATION_FD")
    if raw is None:
        return True
    fd = None
    try:
        fd = int(raw)
        return fd >= 0 and os.read(fd, 1) == b"1"
    except (OSError, ValueError):
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def compose_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
    incident_fingerprint: str = "",
    package_path: str | None = None,
) -> dict:
    if not _await_detach_activation():
        return {"ok": False, "reason": "detachment_not_activated"}
    cfg = load_config(config_path) if live else None
    if live and cfg is not None and cfg.mode != "live":
        return {
            "ok": False,
            "error": "refusing live compose while config mode is not live",
        }
    result = run_path(
        path_id="issue_to_pr",
        repo=repo,
        issue=issue_number,
        config_path=config_path,
        live=live,
        package_path=package_path,
        extra_inputs={
            "incident_fingerprint": incident_fingerprint,
            "keep_issue_open": bool(incident_fingerprint),
        },
    )
    result.update(kind="issue_to_pr", engine="fala", planned=not live)
    try:
        if cfg is not None:
            append_event(cfg.state_path, result)
    except Exception:
        pass
    return result


def main(argv=None):
    p = argparse.ArgumentParser(prog="lokay-issue-to-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    a = p.parse_args(argv)
    return emit_exit(
        compose_issue_to_pr(
            config_path=a.config, repo=a.repo, issue_number=a.issue, live=bool(a.live)
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
