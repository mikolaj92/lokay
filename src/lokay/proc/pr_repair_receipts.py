"""Durable confirmed PR-repair receipts, bounded by request_changes policy.

``limits.max_request_changes_per_pr`` controls how many confirmed repairs one
PR may receive; ``max_repairs_per_tick`` is only a factory-pass fleet limit.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


def receipts_dir(
    *, home: Path | str | None = None, state_dir: Path | str | None = None
) -> Path:
    if state_dir is not None:
        return Path(state_dir).expanduser().resolve() / "pr-repair-receipts"
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / ".lokay" / "pr-repair-receipts"


def receipt_path(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> Path:
    slug = f"{str(repo).replace('/', '__')}__{int(pr)}.json"
    return receipts_dir(home=home, state_dir=state_dir) / slug


def resolve_state_dir(config_path: str | None) -> Path | None:
    if not config_path:
        return None
    try:
        from lokay.config import load_config

        return load_config(config_path).state_path.expanduser().resolve().parent
    except (OSError, ValueError, FileNotFoundError, TypeError):
        return None


def resolve_budget(config_path: str | None) -> int:
    """Per-PR confirmed-repair cap, independent of fleet tick capacity."""
    if not config_path:
        return 1
    try:
        from lokay.config import load_config

        return max(1, int(load_config(config_path).max_request_changes_per_pr))
    except (OSError, ValueError, FileNotFoundError, TypeError):
        return 1


def _empty(repo: str, pr: int, *, budget: int = 1) -> dict[str, Any]:
    return {
        "repo": str(repo),
        "pr": int(pr),
        "attempts": 0,
        "budget": max(1, int(budget)),
        "last_head_sha": "",
        "last_terminal": "",
        "updated_at": "",
        "parked": False,
    }


_SHA = re.compile(r"^[a-f0-9]{40}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_INTENT_SCHEMA = "lokay.pr-repair-push-intent/1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _intent_core(intent: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in intent.items()
        if key not in {"intent_sha256", "push_attempted", "push_attempted_at"}
    }


def _intent_sha256(intent: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(_intent_core(intent))).hexdigest()


def _validate_intent(intent: Any, *, repo: str, pr: int) -> dict[str, Any]:
    if not isinstance(intent, Mapping):
        raise ValueError("repair push intent must be an object")
    value = dict(intent)
    required = {
        "schema", "repo", "pr", "branch", "repair_kind", "start_head_sha",
        "target_head_sha", "reviewed_head_sha", "task_identity_sha256",
        "review_result_sha256", "findings_sha256", "intent_sha256",
        "push_attempted", "push_attempted_at",
    }
    if set(value) != required:
        raise ValueError("repair push intent fields are incomplete or unknown")
    if (
        value.get("schema") != _INTENT_SCHEMA
        or value.get("repo") != repo
        or value.get("pr") != int(pr)
        or not str(value.get("branch") or "").strip()
        or value.get("repair_kind") not in {"ci", "review"}
    ):
        raise ValueError("repair push intent identity mismatch")
    start = str(value.get("start_head_sha") or "").lower()
    target = str(value.get("target_head_sha") or "").lower()
    if not _SHA.fullmatch(start) or not _SHA.fullmatch(target) or start == target:
        raise ValueError("repair push intent must bind distinct full commit SHAs")
    if not isinstance(value.get("push_attempted"), bool) or not isinstance(value.get("push_attempted_at"), str):
        raise ValueError("repair push attempt state is malformed")
    if value["push_attempted"]:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value["push_attempted_at"]):
            raise ValueError("repair push attempt timestamp is malformed")
    elif value["push_attempted_at"]:
        raise ValueError("unattempted repair push has an attempt timestamp")
    if value["repair_kind"] == "review":
        if (
            str(value.get("reviewed_head_sha") or "").lower() != start
            or not _HASH.fullmatch(str(value.get("task_identity_sha256") or ""))
            or not _HASH.fullmatch(str(value.get("review_result_sha256") or ""))
            or not _HASH.fullmatch(str(value.get("findings_sha256") or ""))
        ):
            raise ValueError("review repair push intent is not bound to complete review evidence")
    elif any(str(value.get(key) or "") for key in (
        "reviewed_head_sha", "task_identity_sha256", "review_result_sha256", "findings_sha256",
    )):
        raise ValueError("CI repair push intent contains review-only evidence")
    digest = str(value.get("intent_sha256") or "")
    if not _HASH.fullmatch(digest) or digest != _intent_sha256(value):
        raise ValueError("repair push intent digest mismatch")
    return value


def _read_unlocked(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return {}
    except OSError:
        raise
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("repair receipt is not a regular file")
        try:
            data = json.load(stream)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("repair receipt is malformed") from exc
    if not isinstance(data, dict):
        raise ValueError("repair receipt must be an object")
    if data.get("repo") != repo or int(data.get("pr") or 0) != int(pr):
        raise ValueError("repair receipt identity mismatch")
    try:
        attempts = int(data.get("attempts") or 0)
        budget = int(data.get("budget") or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("repair receipt counters are malformed") from exc
    if attempts < 0 or budget < 1:
        raise ValueError("repair receipt counters are out of range")
    if not isinstance(data.get("parked", False), bool):
        raise ValueError("repair receipt parked flag is malformed")
    if "pending_push" in data and data["pending_push"] is None and attempts and (
        "last_intent_sha256" in data or "last_head_sha" in data
    ):
        if (
            not _HASH.fullmatch(str(data.get("last_intent_sha256") or ""))
            or not _SHA.fullmatch(str(data.get("last_head_sha") or "").lower())
            or not str(data.get("last_branch") or "").strip()
            or data.get("last_repair_kind") not in {"ci", "review"}
        ):
            raise ValueError("confirmed repair receipt identity is incomplete")
    if data.get("publication_checkpoint") is not None:
        proof = data["publication_checkpoint"]
        if not isinstance(proof, dict):
            raise ValueError("repair checkpoint malformed")
        digest = proof.get("sha256")
        if digest != hashlib.sha256(_canonical({k: v for k, v in proof.items() if k != "sha256"})).hexdigest():
            raise ValueError("repair checkpoint digest mismatch")
        _validate_intent(proof.get("intent"), repo=repo, pr=pr)
        if proof.get("schema") != "lokay.pr-repair-checkpoint/1":
            raise ValueError("repair checkpoint schema mismatch")
    if data.get("pending_push") is not None:
        data["pending_push"] = _validate_intent(data["pending_push"], repo=repo, pr=pr)
        if data.get("last_intent_sha256") and int(data.get("attempts") or 0) == 0:
            raise ValueError("pending repair push conflicts with confirmed receipt")
    if data.get("last_branch") is not None and not str(data.get("last_branch") or "").strip():
        raise ValueError("confirmed repair branch is malformed")
    if data.get("last_repair_kind") is not None and data.get("last_repair_kind") not in {"ci", "review"}:
        raise ValueError("confirmed repair kind is malformed")
    if data.get("last_intent_sha256") is not None:
        digest = str(data.get("last_intent_sha256") or "")
        if not _HASH.fullmatch(digest):
            raise ValueError("confirmed repair intent digest is malformed")
        if (
            not _SHA.fullmatch(str(data.get("last_head_sha") or "").lower())
            or not str(data.get("last_branch") or "").strip()
            or data.get("last_repair_kind") not in {"ci", "review"}
            or attempts <= 0
        ):
            raise ValueError("confirmed repair intent identity is incomplete")
    if data.get("last_head_sha"):
        last_head = str(data["last_head_sha"]).lower()
        if not _SHA.fullmatch(last_head):
            raise ValueError("confirmed repair head SHA is malformed")
        data["last_head_sha"] = last_head
    if data.get("last_reviewed_sha"):
        last_reviewed = str(data["last_reviewed_sha"]).lower()
        if not _SHA.fullmatch(last_reviewed):
            raise ValueError("confirmed reviewed SHA is malformed")
        data["last_reviewed_sha"] = last_reviewed
        if data.get("last_head_sha") and last_reviewed == data["last_head_sha"]:
            raise ValueError("confirmed repair must differ from reviewed SHA")
    if data.get("last_intent_sha256") and not str(data.get("last_terminal") or "").strip():
        raise ValueError("confirmed repair terminal is missing")
    if "last_intent_sha256" in data and data.get("last_intent_sha256") is None:
        raise ValueError("confirmed repair intent digest is malformed")
    if "last_head_sha" in data and data.get("last_head_sha") is None:
        raise ValueError("confirmed repair head SHA is malformed")
    if "last_reviewed_sha" in data and data.get("last_reviewed_sha") is None:
        raise ValueError("confirmed reviewed SHA is malformed")
    return data


def _write_unlocked(repo: str, pr: int, payload: Mapping[str, Any], *, home=None, state_dir=None) -> dict[str, Any]:
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise
    return dict(payload)


@contextmanager
def _locked(repo: str, pr: int, *, home=None, state_dir=None) -> Iterator[None]:
    directory = receipts_dir(home=home, state_dir=state_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("repair receipt lock is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def read(
    repo: str, pr: int, *, home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _read_unlocked(repo, pr, home=home, state_dir=state_dir)


def _write(repo: str, pr: int, payload: Mapping[str, Any], *, home=None, state_dir=None) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _write_unlocked(repo, pr, payload, home=home, state_dir=state_dir)


def prepare_push_intent(
    *, repo: str, pr: int, intent: Mapping[str, Any], budget: int = 1,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _prepare_push_intent_unlocked(
            repo=repo, pr=pr, intent=intent, budget=budget,
            home=home, state_dir=state_dir,
        )


def record_publication_checkpoint(*, proof: dict, state_dir: Path, budget: int) -> dict:
    """Retain verified prepublication evidence under the existing receipt lock."""
    intent = proof["intent"]
    repo, pr = intent["repo"], intent["pr"]
    _validate_intent(intent, repo=repo, pr=pr)
    with _locked(repo, pr, state_dir=state_dir):
        previous = _read_unlocked(repo, pr, state_dir=state_dir)
        existing = previous.get("publication_checkpoint")
        if existing and existing != proof:
            if (previous.get("checkpoint_terminal") != "confirmed_target"
                    or intent["start_head_sha"] != previous.get("last_head_sha")):
                return {"ok": True, "route": "fail_closed", "reason": "repair_checkpoint_conflict"}
            previous.setdefault("checkpoint_history", []).append({
                "checkpoint": existing, "terminal": previous.pop("checkpoint_terminal"),
            })
            existing = None
        if previous.get("pending_push") and previous["pending_push"]["intent_sha256"] != intent["intent_sha256"]:
            return {"ok": True, "route": "fail_closed", "reason": "repair_checkpoint_conflict"}
        if int(previous.get("attempts") or 0) >= budget:
            return {"ok": True, "route": "fail_closed", "reason": "pr_repair_budget_exhausted"}
        if not existing:
            base = {**_empty(repo, pr, budget=budget), **previous, "publication_checkpoint": proof}
            _write_unlocked(repo, pr, base, state_dir=state_dir)
        return {"ok": True, "route": "checkpointed", "checkpoint_sha256": proof["sha256"]}


def mark_push_attempted(
    *, repo: str, pr: int, intent_sha256: str,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _mark_push_attempted_unlocked(
            repo=repo, pr=pr, intent_sha256=intent_sha256,
            home=home, state_dir=state_dir,
        )


def confirm_pending_push(
    *, repo: str, pr: int, intent_sha256: str, remote_head_sha: str,
    remote_branch: str, remote_repo: str, remote_state: str, budget: int = 1,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _confirm_pending_push_unlocked(
            repo=repo, pr=pr, intent_sha256=intent_sha256,
            remote_head_sha=remote_head_sha, remote_branch=remote_branch,
            remote_repo=remote_repo, remote_state=remote_state, budget=budget,
            home=home, state_dir=state_dir,
        )


def stamp(
    repo: str, pr: int, *, attempt_delta: int = 1, head_sha: str = "",
    reviewed_sha: str = "", terminal: str = "", budget: int = 1,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _stamp_unlocked(
            repo, pr, attempt_delta=attempt_delta, head_sha=head_sha,
            reviewed_sha=reviewed_sha, terminal=terminal, budget=budget,
            home=home, state_dir=state_dir,
        )


def clear(
    repo: str, pr: int, *, home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> bool:
    with _locked(repo, pr, home=home, state_dir=state_dir):
        return _clear_unlocked(repo, pr, home=home, state_dir=state_dir)


def build_push_intent(
    *, repo: str, pr: int, branch: str, repair_kind: str,
    start_head_sha: str, target_head_sha: str, reviewed_head_sha: str = "",
    task: Mapping[str, Any] | None = None, findings: list[dict[str, Any]] | None = None,
    task_identity_sha256: str = "", review_result_sha256: str = "",
) -> dict[str, Any]:
    start = str(start_head_sha or "").lower()
    target = str(target_head_sha or "").lower()
    task_digest = str(task_identity_sha256 or "").lower()
    result_digest = str(review_result_sha256 or "").lower()
    findings_digest = ""
    if repair_kind == "review":
        canonical_task = dict(task or {})
        all_findings = list(findings or [])
        actual_task_digest = hashlib.sha256(_canonical(canonical_task)).hexdigest()
        if actual_task_digest != task_digest or not canonical_task or not all_findings:
            raise ValueError("review repair push intent requires matching task and findings")
        findings_digest = hashlib.sha256(_canonical(all_findings)).hexdigest()
        if str(reviewed_head_sha or "").lower() != start:
            raise ValueError("review repair push start must equal reviewed head")
    elif repair_kind == "ci":
        if task or findings or reviewed_head_sha or task_digest or result_digest:
            raise ValueError("CI repair push intent cannot contain review handoff")
    else:
        raise ValueError("repair kind must be ci or review")
    intent: dict[str, Any] = {
        "schema": _INTENT_SCHEMA,
        "repo": repo,
        "pr": int(pr),
        "branch": str(branch),
        "repair_kind": repair_kind,
        "start_head_sha": start,
        "target_head_sha": target,
        "reviewed_head_sha": str(reviewed_head_sha or "").lower(),
        "task_identity_sha256": task_digest,
        "review_result_sha256": result_digest,
        "findings_sha256": findings_digest,
        "push_attempted": False,
        "push_attempted_at": "",
    }
    intent["intent_sha256"] = _intent_sha256(intent)
    return _validate_intent(intent, repo=repo, pr=pr)


def _prepare_push_intent_unlocked(
    *, repo: str, pr: int, intent: Mapping[str, Any], budget: int = 1,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    prepared = _validate_intent(intent, repo=repo, pr=pr)
    previous = _read_unlocked(repo, pr, home=home, state_dir=state_dir)
    base = _empty(repo, pr, budget=max(1, int(budget)))
    base.update(previous)
    checkpoint = previous.get("publication_checkpoint")
    if checkpoint and (previous.get("checkpoint_terminal")
                       or checkpoint["intent"]["intent_sha256"] != prepared["intent_sha256"]):
        return {"ok": True, "route": "fail_closed", "reason": "repair_checkpoint_intent_mismatch"}
    if previous and int(previous.get("budget") or 0) != max(1, int(budget)):
        base["parked"] = int(previous.get("attempts") or 0) >= max(1, int(budget))
    if base.get("pending_push") is not None:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_intent_already_pending"}
    if int(base.get("attempts") or 0) >= int(budget):
        return {"ok": True, "route": "fail_closed", "reason": "pr_repair_budget_exhausted"}
    previous_head = str(base.get("last_head_sha") or "").lower()
    if int(base.get("attempts") or 0) and prepared["start_head_sha"] != previous_head:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_start_head_drift"}
    if previous_head == prepared["target_head_sha"]:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_target_already_recorded"}
    base.update(repo=repo, pr=int(pr), budget=max(1, int(budget)), pending_push=prepared)
    try:
        _write_unlocked(repo, pr, base, home=home, state_dir=state_dir)
    except OSError:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_intent_persist_failed"}
    return {"ok": True, "route": "recorded", "intent_sha256": prepared["intent_sha256"]}


def _mark_push_attempted_unlocked(
    *, repo: str, pr: int, intent_sha256: str,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    receipt = _read_unlocked(repo, pr, home=home, state_dir=state_dir)
    pending = receipt.get("pending_push")
    if not isinstance(pending, Mapping) or pending.get("intent_sha256") != intent_sha256:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_intent_missing_or_drifted"}
    if pending.get("push_attempted"):
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_attempt_already_started"}
    pending = {**dict(pending), "push_attempted": True,
               "push_attempted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    receipt["pending_push"] = pending
    try:
        _write_unlocked(repo, pr, receipt, home=home, state_dir=state_dir)
    except OSError:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_attempt_persist_failed"}
    return {"ok": True, "route": "ready", "intent_sha256": intent_sha256}


def _confirm_pending_push_unlocked(
    *, repo: str, pr: int, intent_sha256: str, remote_head_sha: str,
    remote_branch: str, remote_repo: str, remote_state: str, budget: int = 1,
    home: Path | str | None = None, state_dir: Path | str | None = None,
) -> dict[str, Any]:
    receipt = _read_unlocked(repo, pr, home=home, state_dir=state_dir)
    if receipt.get("pending_push") is None:
        if receipt.get("last_intent_sha256") == intent_sha256:
            if str(receipt.get("last_head_sha") or "").lower() != str(remote_head_sha or "").lower():
                return {"ok": True, "route": "fail_closed", "reason": "repair_push_remote_identity_mismatch"}
            if remote_branch != str(receipt.get("last_branch") or ""):
                return {"ok": True, "route": "fail_closed", "reason": "repair_push_remote_identity_mismatch"}
            if str(remote_repo or "").lower() != repo.lower() or str(remote_state or "").upper() != "OPEN":
                return {"ok": True, "route": "fail_closed", "reason": "repair_push_remote_identity_mismatch"}
            return {"ok": True, "route": "confirmed", "already_confirmed": True,
                    "attempts": int(receipt.get("attempts") or 0),
                    "budget": int(receipt.get("budget") or budget),
                    "parked": bool(receipt.get("parked")),
                    "head_sha": str(receipt.get("last_head_sha") or ""),
                    "reviewed_sha": str(receipt.get("last_reviewed_sha") or ""),
                    "repair_kind": str(receipt.get("last_repair_kind") or "")}
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_intent_missing"}
    pending = _validate_intent(receipt["pending_push"], repo=repo, pr=pr)
    if pending["intent_sha256"] != intent_sha256:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_intent_identity_mismatch"}
    if not pending.get("push_attempted"):
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_not_started"}
    if (
        str(remote_head_sha or "").lower() != pending["target_head_sha"]
        or remote_branch != pending["branch"]
        or str(remote_repo or "").lower() != repo.lower()
        or str(remote_state or "").upper() != "OPEN"
    ):
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_remote_identity_mismatch"}
    if receipt.get("publication_checkpoint"):
        receipt["checkpoint_terminal"] = "confirmed_target"
    attempts = int(receipt.get("attempts") or 0) + 1
    budget_n = max(1, int(budget or receipt.get("budget") or 1))
    parked = attempts >= budget_n
    receipt.update({
        "repo": repo, "pr": int(pr), "attempts": attempts, "budget": budget_n,
        "last_reviewed_sha": pending["start_head_sha"],
        "last_head_sha": pending["target_head_sha"],
        "last_branch": pending["branch"],
        "last_terminal": "publish", "last_intent_sha256": pending["intent_sha256"],
        "last_repair_kind": pending["repair_kind"],
        "parked": parked, "pending_push": None,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    try:
        _write_unlocked(repo, pr, receipt, home=home, state_dir=state_dir)
    except OSError:
        return {"ok": True, "route": "fail_closed", "reason": "repair_push_confirmation_persist_failed"}
    return {"ok": True, "route": "confirmed", "already_confirmed": False,
            "attempts": attempts, "budget": budget_n, "parked": parked,
            "head_sha": pending["target_head_sha"],
            "reviewed_sha": pending["start_head_sha"],
            "repair_kind": pending["repair_kind"]}


def _stamp_unlocked(
    repo: str,
    pr: int,
    *,
    attempt_delta: int = 1,
    head_sha: str = "",
    reviewed_sha: str = "",
    terminal: str = "",
    budget: int = 1,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Increment legacy/manual receipts; never overwrite a write-ahead intent."""
    budget_n = max(1, int(budget))
    previous = _read_unlocked(repo, pr, home=home, state_dir=state_dir)
    base = _empty(repo, pr, budget=budget_n)
    if previous:
        if previous.get("pending_push") is not None:
            raise ValueError("cannot stamp while a repair push intent is pending")
        base.update(previous)
        # Keep an existing budget unless caller raises it explicitly via arg
        # and receipt had none; prefer stamped budget arg as the live K.
        base["budget"] = budget_n
    if head_sha and head_sha == reviewed_sha:
        raise ValueError("repaired SHA must differ from reviewed SHA")
    previous_head = str(base.get("last_head_sha") or "")
    if head_sha and previous_head == head_sha:
        raise ValueError("repair receipt already records this pushed SHA")
    attempts = max(0, int(base.get("attempts") or 0)) + int(attempt_delta)
    parked = attempts >= budget_n
    payload: dict[str, Any] = {
        "repo": str(repo),
        "pr": int(pr),
        "attempts": attempts,
        "budget": budget_n,
        "last_reviewed_sha": str(reviewed_sha or base.get("last_reviewed_sha") or ""),
        "last_head_sha": str(head_sha or base.get("last_head_sha") or ""),
        "last_terminal": str(terminal or base.get("last_terminal") or ""),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parked": parked,
    }
    try:
        return _write_unlocked(repo, pr, payload, home=home, state_dir=state_dir)
    except OSError:
        # Legacy callers still receive the logical receipt so they can park.
        return payload


def _clear_unlocked(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> bool:
    """Drop receipt when PR is gone (merge/close); optional reset."""
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
