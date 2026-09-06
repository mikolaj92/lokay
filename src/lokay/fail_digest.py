"""Short human-readable digest when a Fala run ends ok:false.

Pure template — no LLM. Writes next to lokay state (beside last-pass), never
raises into the daemon. Fail-closed: missing evidence still yields a short note.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DIGEST_NAME = "fail-digest-latest.md"
DIGEST_DIR = "fail-digests"
_MSG_LIMIT = 800
_INSUFFICIENT = "insufficient evidence"

_SECRET_RE = re.compile(
    r"(?i)(ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"gho_[A-Za-z0-9_]{20,}|ghu_[A-Za-z0-9_]{20,}|"
    r"Bearer\s+[A-Za-z0-9._\-]+|"
    r"token[=:\s]+[A-Za-z0-9._\-]{16,})"
)


def resolve_state_dir(config_path: str | Path | None = None) -> Path:
    """State directory that holds last-pass.json (parent of state.path)."""
    if config_path:
        try:
            from lokay.config import load_config

            return load_config(str(config_path)).state_path.expanduser().resolve().parent
        except Exception:
            pass
    return (Path.home() / ".lokay").expanduser().resolve()


def build_digest(envelope: Any) -> str:
    """Render a 10–20 line plain-text digest from an ok:false envelope."""
    try:
        return _build_digest(envelope)
    except Exception as exc:  # never crash callers
        return (
            "# Fail-run digest\n\n"
            f"- status: {_INSUFFICIENT}\n"
            f"- note: digest builder fault ({type(exc).__name__})\n"
            "- co dalej:\n"
            "  - inspect last Fala journal / launchd log; do not treat this as DoD progress\n"
        )


def write_digest(state_dir: Path | str | None, envelope: Any) -> Path | None:
    """Persist digest under state_dir. Never raises. No-op when ok is not false."""
    try:
        if not isinstance(envelope, dict) or envelope.get("ok") is not False:
            return None
        if state_dir is None:
            return None
        root = Path(state_dir).expanduser()
        text = build_digest(envelope)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = _safe_slug(_first_str(envelope, "run_id") or _first_str(envelope, "path_id") or "unknown")
        archive_dir = root / DIGEST_DIR
        archive_dir.mkdir(parents=True, exist_ok=True)
        archived = archive_dir / f"{stamp}-{run_id}.md"
        latest = root / DIGEST_NAME
        archived.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
        return latest
    except Exception:
        return None


def _build_digest(envelope: Any) -> str:
    if not isinstance(envelope, dict):
        return (
            "# Fail-run digest\n\n"
            f"- status: {_INSUFFICIENT}\n"
            "- note: envelope is not a dict\n"
            "- co dalej:\n"
            "  - re-run with structured Fala output; digest needs an ok:false envelope\n"
        )

    path_id = _first_str(envelope, "path_id") or _nested_path_id(envelope) or "?"
    run_id = _first_str(envelope, "run_id") or "?"
    atom = _atom_of(envelope) or "?"
    health = _first_str(envelope, "health") or "?"
    reason = _first_str(envelope, "reason") or ""
    code = _error_code(envelope)
    exit_info = _exit_signal(envelope)
    message = _short_message(envelope)
    next_lines = _next_steps(envelope, message)

    lines = [
        "# Fail-run digest",
        "",
        f"- path_id: {path_id}",
        f"- atom/effector: {atom}",
        f"- run_id: {run_id}",
        f"- health: {health}" + (f" reason={reason}" if reason else ""),
    ]
    if code:
        lines.append(f"- error.code: {code}")
    if exit_info:
        lines.append(f"- exit/signal: {exit_info}")
    lines.append(f"- message: {message or _INSUFFICIENT}")
    lines.append("- co dalej:")
    for tip in next_lines:
        lines.append(f"  - {tip}")
    lines.append("")
    lines.append(
        "_Note: fail digest is diagnostic only — not Definition of Done progress._"
    )
    lines.append("")
    # Keep short: hard-cap ~20 content lines (title + blanks already few).
    body = "\n".join(lines)
    content_lines = [ln for ln in body.splitlines() if ln.strip()]
    if len(content_lines) > 22:
        trimmed = "\n".join(body.splitlines()[:24])
        return trimmed.rstrip() + "\n"
    return body if body.endswith("\n") else body + "\n"


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _first_str(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _nested_path_id(envelope: dict[str, Any]) -> str:
    for key in ("lokay", "last", "terminal"):
        nested = _as_dict(envelope.get(key))
        if nested and _first_str(nested, "path_id"):
            return _first_str(nested, "path_id")
    return ""


def _atom_of(envelope: dict[str, Any]) -> str:
    for key in ("last_atom", "atom", "effector", "step"):
        if _first_str(envelope, key):
            return _first_str(envelope, key)
    failed = _failed_step(envelope)
    if failed:
        for key in ("step", "atom", "effector", "id"):
            if _first_str(failed, key):
                return _first_str(failed, key)
    terminal = _as_dict(envelope.get("terminal"))
    if terminal:
        for name, item in terminal.items():
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            if status in {"failed", "error", "timed_out", "cancelled", "canceled"}:
                return str(name)
            if item.get("ok") is False:
                return str(name)
    steps = envelope.get("steps")
    if isinstance(steps, list):
        for item in steps:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            if status in {"failed", "error", "timed_out"} or item.get("ok") is False:
                return _first_str(item, "step") or _first_str(item, "atom") or "?"
    return ""


def _failed_step(envelope: dict[str, Any]) -> dict[str, Any] | None:
    steps = envelope.get("steps")
    if isinstance(steps, list):
        for item in steps:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            if status in {"failed", "error", "timed_out", "cancelled", "canceled"}:
                return item
            if item.get("ok") is False:
                return item
    terminal = _as_dict(envelope.get("terminal"))
    if terminal:
        for name, item in terminal.items():
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            if status in {"failed", "error", "timed_out"} or item.get("ok") is False:
                return {"step": name, **item}
    return None


def _error_code(envelope: dict[str, Any]) -> str:
    for source in (envelope, _as_dict(envelope.get("error")), _failed_step(envelope)):
        if not isinstance(source, dict):
            continue
        code = source.get("code")
        if code not in (None, ""):
            return str(code)
        err = source.get("error")
        if isinstance(err, dict) and err.get("code") not in (None, ""):
            return str(err["code"])
    return ""


def _exit_signal(envelope: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("exit", "exit_code", "returncode", "signal"):
        value = envelope.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    failed = _failed_step(envelope)
    if failed:
        for key in ("exit", "exit_code", "returncode", "signal"):
            value = failed.get(key)
            if value not in (None, "") and f"{key}=" not in " ".join(parts):
                parts.append(f"{key}={value}")
    text = _flatten_text(envelope)
    match = re.search(r"\bexit(?:_code)?[=:\s]+(-?\d+)", text, re.I)
    if match and "exit" not in " ".join(parts):
        parts.append(f"exit={match.group(1)}")
    match = re.search(r"\bsignal[=:\s]+([A-Za-z0-9_]+)", text, re.I)
    if match and "signal" not in " ".join(parts):
        parts.append(f"signal={match.group(1)}")
    return ", ".join(parts)


def _short_message(envelope: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("error", "error_json", "message", "stderr"):
        value = envelope.get(key)
        if value in (None, "", {}, []):
            continue
        chunks.append(_stringify(value))
    failed = _failed_step(envelope)
    if failed:
        for key in ("error", "error_json", "message", "stderr"):
            value = failed.get(key)
            if value in (None, "", {}, []):
                continue
            chunks.append(_stringify(value))
    fala = _as_dict(envelope.get("fala"))
    if fala:
        for key in ("error", "message"):
            if fala.get(key) not in (None, "", {}):
                chunks.append(_stringify(fala.get(key)))
    raw = " | ".join(c for c in chunks if c).strip()
    if not raw:
        reason = _first_str(envelope, "reason")
        raw = reason or _INSUFFICIENT
    return _truncate(_redact(raw), _MSG_LIMIT)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return _stringify(json.loads(text))
            except (TypeError, ValueError):
                return text
        return text
    if isinstance(value, dict):
        # Prefer nested message / traceback fields when present.
        for key in ("message", "traceback", "error", "stderr", "detail", "reason"):
            if value.get(key) not in (None, "", {}, []):
                nested = _stringify(value.get(key))
                code = value.get("code")
                if code not in (None, "") and nested:
                    return f"[{code}] {nested}"
                return nested
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, list):
        return " | ".join(_stringify(item) for item in value[:5] if item not in (None, ""))
    return str(value)


def _flatten_text(envelope: dict[str, Any]) -> str:
    parts = [
        _short_message(envelope),
        _first_str(envelope, "reason"),
        _first_str(envelope, "health"),
        _first_str(envelope, "code"),
        _atom_of(envelope),
        _first_str(envelope, "path_id"),
    ]
    failed = _failed_step(envelope)
    if failed:
        parts.append(_stringify(failed))
    return " ".join(p for p in parts if p).lower()


def _next_steps(envelope: dict[str, Any], message: str) -> list[str]:
    text = f"{message} {_flatten_text(envelope)}".lower()
    tips: list[str] = []

    def add(tip: str) -> None:
        if tip not in tips:
            tips.append(tip)

    if "checkout is dirty" in text or ("host_ff" in text and "dirty" in text) or (
        "dirty" in text and "host" in text
    ):
        add("host checkout dirty — clean or commit local changes before host_ff / park the slot")
    if any(
        token in text
        for token in (
            "python_syntax",
            "syntaxerror",
            "coding_boundary",
            "traceback",
            "integrity",
        )
    ):
        add("coding/integrity fault — inspect syntax or coding_boundary output; do not merge")
    err_only = str(message or "").lower()
    if "adapter_failed" in text or "subprocess adapter failed" in text:
        if _empty_adapter(err_only) or _empty_adapter(
            str(envelope.get("error") or "").lower()
        ):
            add(
                "empty adapter_failed — check organ cwd (sqlite.fire inheritance) and effector stderr"
            )
        else:
            add("adapter_failed — open the failed effector stderr / error_json in the Fala journal")
    if "pass_ceiling" in text or "ceiling_" in text:
        add("pass_ceiling — caretaker released the daemon slot; check inflight working / last-pass")
    if "preflight_failed" in text or ("preflight" in text and "fail" in text):
        add("preflight_failed — fix carrier health (lock/lease/disk/gh) before product work")
    if "issue_sieve" in text:
        add("issue_sieve failure — inspect sieve row envelope; park or re-triage the ticket")
    if "park" in text and "slot" in text:
        add("park the busy slot / wait for the overlapping worker to finish")
    if not tips:
        if message == _INSUFFICIENT or not message:
            add("insufficient structured error — check ~/.lokay/fala journal and launchd log")
        else:
            add("inspect fail-digest-latest.md + last-pass; digest ≠ DoD progress")
        add("re-run lokay status --local after the next tick")
    return tips[:3]


def _empty_adapter(text: str) -> bool:
    if "adapter_failed" not in text and "subprocess adapter failed" not in text:
        return False
    remainder = text
    for token in (
        "adapter_failed",
        "subprocess adapter failed",
        "code",
        "message",
        "error",
        "error_json",
    ):
        remainder = re.sub(re.escape(token), " ", remainder, flags=re.IGNORECASE)
    remainder = re.sub(r"\\[nrt]", " ", remainder)
    remainder = re.sub(r"[^A-Za-z0-9]+", "", remainder)
    return remainder == ""


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text)


def _truncate(text: str, limit: int) -> str:
    text = text.replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _safe_slug(raw: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(raw).strip())[:80]
    return slug or "unknown"
