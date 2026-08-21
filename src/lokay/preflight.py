"""Fail-closed self-health gate and bounded incident reporting."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import shutil
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

from lokay.config import load_config

_REDACTED = "[redacted]"
_LOCKS: dict[str, Any] = {}
_DEFAULT_INCIDENT_REPO = "mikolaj92/lokay"
_DEFAULT_INCIDENT_COOLDOWN_HOURS = 12.0
_ISSUE_NUMBER_RE = re.compile(r"/issues/(\d+)(?:\s|$)")
INCIDENT_TTL_SECONDS = 300
IDLE_INCIDENT_TTL_SECONDS = 900
INCIDENT_STAMP_NAME = "preflight-incident-close.stamp"


def trusted_fala_manifest() -> Path:
    """Return the canonical manifest from a checkout or installed wheel."""
    here = Path(__file__).resolve()
    packaged = here.parent / "data" / "lokay.fala-package.toml"
    if not packaged.is_file():
        raise RuntimeError("packaged Fala manifest unavailable")

    # Only compare against the checkout that owns this module. An installed
    # wheel may be started with a checkout as its working directory while that
    # checkout is being upgraded; treating that unrelated CWD as wheel
    # provenance makes the otherwise self-contained carrier fail transiently.
    source_candidate = here.parents[2] / "fala" / "lokay.fala-package.toml"
    source = source_candidate if source_candidate.is_file() else None
    if source is not None and source.read_bytes() != packaged.read_bytes():
        raise RuntimeError("canonical Fala manifests differ")

    trusted = source or packaged
    override = os.environ.get("LOKAY_FALA_PACKAGE")
    if override:
        selected = Path(override).expanduser().resolve()
        canonical = {packaged.resolve(), *(set() if source is None else {source.resolve()})}
        if selected not in canonical:
            raise RuntimeError("untrusted LOKAY_FALA_PACKAGE override")
        return selected
    return trusted


def _finding(name: str, passed: bool, code: str, *, repaired: bool = False) -> dict[str, Any]:
    return {"name": name, "ok": passed, "code": code[:80], "detail": code[:80], "repaired": repaired}


def _fala_smoke() -> tuple[bool, str]:
    """Validate the in-process Fala API and every workflow Lokay requires."""
    try:
        from fala import host_run_package, sdk

        package = trusted_fala_manifest()
        manifest = tomllib.loads(package.read_text(encoding="utf-8"))
        paths = {
            str(item.get("id"))
            for item in manifest.get("correlation_paths", [])
            if isinstance(item, dict)
        }
        required = {
            "factory_pass", "issue_to_pr", "issue_triage", "pr_repair",
            "pr_triage", "self_repair",
        }
        ok = callable(host_run_package) and callable(sdk.conduction) and required <= paths
        return ok, "ok" if ok else "incompatible_api_or_manifest"
    except (ImportError, AttributeError, OSError, RuntimeError, tomllib.TOMLDecodeError) as exc:
        return False, f"unavailable_{type(exc).__name__}"


def _canonical_github_ssh(repo_name: str) -> str:
    return f"git@github.com:{repo_name}.git"


def _github_git_transport(cfg: Any) -> tuple[bool, str]:
    """Prove the mill checkout uses the authenticated SSH carrier."""
    from lokay.preflight_checks import preflight_repos

    repos = preflight_repos(cfg)
    checked = 0
    for repo in repos:
        if not (repo.clone_path / ".git").exists():
            continue
        checked += 1
        try:
            remote = subprocess.run(
                ["git", "-C", str(repo.clone_path), "remote", "get-url", "origin"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.TimeoutExpired):
            return False, "origin_unavailable"
        if remote.returncode != 0:
            # Missing origin is not a protocol mismatch — fail closed honestly.
            return False, "origin_unavailable"
        current = getattr(remote, "stdout", "").strip()
        if current != _canonical_github_ssh(repo.name):
            return False, "non_ssh_origin"
    if checked == 0:
        return True, "ok"
    from lokay.git_host_ff import caretaker_already_fetched

    if caretaker_already_fetched():
        # mill-daemon already fetched origin/main this tick. Origin URL is
        # still checked above; do not ls-remote the same checkout twice.
        return True, "ok"
    probe = next(repo for repo in repos if (repo.clone_path / ".git").exists())
    authenticated = False
    # Keep the original 20-second bound, but do not stop the mill for a single
    # transient SSH/network failure.  Both attempts remain non-interactive and
    # must prove access to the canonical origin.
    for _attempt in range(2):
        try:
            authenticated = subprocess.run(
                ["git", "-C", str(probe.clone_path), "ls-remote", "--exit-code", "origin", "HEAD"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes"},
            ).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            authenticated = False
        if authenticated:
            break
    return authenticated, "ok" if authenticated else "ssh_auth_unavailable"


def _repair_github_git_transport(cfg: Any) -> bool:
    """Replace the mill checkout's canonical HTTPS origin with its SSH form."""
    from lokay.preflight_checks import preflight_repos

    changed = False
    for repo in preflight_repos(cfg):
        if not (repo.clone_path / ".git").exists():
            continue
        try:
            remote = subprocess.run(
                ["git", "-C", str(repo.clone_path), "remote", "get-url", "origin"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            current = getattr(remote, "stdout", "").strip()
            expected_https = f"https://github.com/{repo.name}.git"
            if remote.returncode == 0 and current == expected_https:
                updated = subprocess.run(
                    ["git", "-C", str(repo.clone_path), "remote", "set-url", "origin", _canonical_github_ssh(repo.name)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                changed = updated.returncode == 0 or changed
        except (OSError, subprocess.TimeoutExpired):
            continue
    return changed


def _executor_path_candidates() -> tuple[Path, ...]:
    """Return bounded executor directories for service and login homes.

    launchd can start the daemon without HOME.  The shell bootstrap supplies a
    writable fallback in that case, but the executor is still installed under
    the account's real home.  Keep both homes in the small, known install set;
    do not recursively scan the filesystem for binaries.
    """
    homes = [Path.home()]
    try:
        login_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError, AttributeError):
        login_home = None
    if login_home is not None and login_home not in homes:
        homes.append(login_home)
    locations = (
        (".local", "bin"),
        (".local", "share", "mise", "shims"),
        (".pi", "agent", "bin"),
    )
    return tuple(home.joinpath(*parts) for home in homes for parts in locations)


def _repair_runtime_path(command: str) -> bool:
    """Expose user-installed executors when a service inherited a minimal PATH."""
    if shutil.which(command):
        return False
    executor_dir = next(
        (
            path
            for path in _executor_path_candidates()
            if _safe_owned_path(path)
            and path.is_dir()
            and shutil.which(command, path=str(path)) is not None
        ),
        None,
    )
    if executor_dir is None:
        return False
    original = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(part for part in (original, str(executor_dir)) if part)
    return True


def _safe_owned_path(path: Path) -> bool:
    """Reject roots, symlinks, foreign-owned existing ancestors, and traversal."""
    try:
        path = path.expanduser().absolute()
        if path == Path(path.anchor) or ".." in path.parts:
            return False
        current = path
        while not current.exists() and current != current.parent:
            current = current.parent
        if current.is_symlink() or not current.is_dir():
            return False
        # Never create through an existing symlink component.
        probe = Path(path.anchor)
        for part in path.parts[1:]:
            probe /= part
            if probe.exists() and probe.is_symlink():
                return False
        return not hasattr(os, "getuid") or current.stat().st_uid == os.getuid()
    except OSError:
        return False



def _lease_path() -> Path:
    configured = os.environ.get("LOKAY_HEALTH_LEASE_PATH", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".lokay" / "health-lease"
    )


def issue_health_lease(
    *, ttl_seconds: int = 7200, lock_path: Path | None = None
) -> None:
    """Issue a run-scoped capability bound to the lock retained by its owner."""
    import time

    inherited = os.environ.get("LOKAY_HEALTH_LEASE", "")
    disabled = os.environ.get("LOKAY_DISABLE_HEALTH_LEASE_ISSUE") == "1"
    # DISABLE blocks minting a new token. Restoring the same inherited token
    # when the file is gone is not a new capability — detached Fala children
    # inherit DISABLE=1 from the mill and must still mutate after mill revoke.
    if disabled and not inherited:
        return
    if inherited:
        healthy, reason = health_lease_status()
        if healthy:
            return
        # File gone: rewrite the record for the same token so nested atoms can
        # still mutate. Never overwrite an expired/mismatched/present record.
        restorable = (
            str(reason).startswith("lease_unavailable_FileNotFound")
            or str(reason).startswith("lease_unavailable_ProcessLookup")
            or str(reason) == "lock_not_held"
        )
        if not restorable:
            if disabled:
                return
            raise RuntimeError(f"refusing to replace inherited health lease ({reason})")
        if len(inherited) != 64:
            raise RuntimeError(f"refusing to replace inherited health lease ({reason})")
        token = inherited
    else:
        if disabled:
            return
        token = secrets.token_hex(32)
    # The daemon may preselect a per-run path. Standalone callers retain the
    # conventional location for compatibility and tests.
    path = _lease_path()
    if not _safe_owned_path(path.parent):
        raise RuntimeError("unsafe health lease directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    bound_lock = (lock_path or (Path.home() / ".lokay" / "mill.lock")).expanduser().absolute()
    record = {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "owner_pid": os.getpid(),
        "lock_path": str(bound_lock),
        "issued_at": int(time.time()),
        # One factory pass may legitimately spend an hour in the real agent.
        # Owner liveness, the held mill lock, and explicit daemon revocation are
        # the primary lifetime bounds; this cap only limits abandoned records.
        "expires_at": int(time.time()) + max(1, min(int(ttl_seconds), 7200)),
    }
    # Publish through a same-directory exclusive regular temp. O_NOFOLLOW and
    # O_EXCL prevent symlink traversal; atomic replace closes the check/use gap.
    temp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o600)
    try:
        st = os.fstat(fd)
        import stat

        if not stat.S_ISREG(st.st_mode) or (
            hasattr(os, "getuid") and st.st_uid != os.getuid()
        ):
            raise RuntimeError("unsafe health lease temp file")
        os.write(fd, json.dumps(record, sort_keys=True).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        if path.exists() or path.is_symlink():
            existing = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(existing.st_mode) or (
                hasattr(os, "getuid") and existing.st_uid != os.getuid()
            ):
                raise RuntimeError("unsafe existing health lease")
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    os.environ["LOKAY_HEALTH_LEASE"] = token
    os.environ["LOKAY_HEALTH_LEASE_PATH"] = str(path.absolute())


def revoke_health_lease() -> None:
    path = _lease_path()
    token = os.environ.pop("LOKAY_HEALTH_LEASE", "")
    os.environ.pop("LOKAY_HEALTH_LEASE_PATH", None)
    try:
        record = json.loads(path.read_text(encoding="ascii"))
        owned = len(token) == 64 and secrets.compare_digest(
            str(record["token_sha256"]),
            hashlib.sha256(token.encode("ascii")).hexdigest(),
        )
        if owned:
            path.unlink()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass


def health_lease_status(*, lock_path: Path | None = None) -> tuple[bool, str]:
    """Validate the inherited capability and its exact bound run lock."""
    import time

    def lock_is_held(candidate: Path, owner_pid: int) -> bool:
        key = str(candidate)
        if owner_pid == os.getpid() and key in _LOCKS:
            os.fstat(_LOCKS[key].fileno())
            return True
        probe = candidate.open("a+")
        try:
            try:
                fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
            except BlockingIOError:
                return True
            return False
        finally:
            probe.close()

    token = os.environ.get("LOKAY_HEALTH_LEASE", "")
    path = _lease_path()
    try:
        st = path.lstat()
        record = json.loads(path.read_text(encoding="ascii"))
        owner_pid = int(record["owner_pid"])
        try:
            os.kill(owner_pid, 0)
            owner_alive = True
        except OSError:
            owner_alive = False
        expected_lock = lock_path.expanduser().absolute() if lock_path is not None else None
        recorded_lock = record.get("lock_path")
        legacy_lock = (Path.home() / ".lokay" / "mill.lock").absolute()
        # Leases issued by the pre-upgrade daemon implicitly used the HOME
        # lock. During activation, also prove that daemon still holds the exact
        # configured lock before allowing validation to run behind it.
        bound_lock = (
            Path(str(recorded_lock)).expanduser().absolute()
            if recorded_lock is not None
            else expected_lock or legacy_lock
        )
        if expected_lock is not None and recorded_lock is not None and bound_lock != expected_lock:
            return False, "lock_path_mismatch"
        lock_held = lock_is_held(bound_lock, owner_pid)
        if recorded_lock is None and bound_lock != legacy_lock:
            lock_held = lock_held and lock_is_held(legacy_lock, owner_pid)
        # Detached Fala children restore the inherited token into this process
        # and outlive the mill tick that held mill.lock. Owner-is-self is enough.
        if owner_pid == os.getpid():
            lock_held = True
        if not owner_alive and not lock_held:
            return False, "lease_unavailable_ProcessLookupError"
        now = int(time.time())
        checks = (
            (lock_held, "lock_not_held"),
            (len(token) == 64, "token_missing"),
            (not path.is_symlink(), "lease_symlink"),
            (not hasattr(os, "getuid") or st.st_uid == os.getuid(), "wrong_owner"),
            (st.st_mode & 0o077 == 0, "unsafe_mode"),
            (int(record["issued_at"]) <= now < int(record["expires_at"]), "expired"),
            (
                secrets.compare_digest(
                    str(record["token_sha256"]),
                    hashlib.sha256(token.encode("ascii")).hexdigest(),
                ),
                "token_mismatch",
            ),
        )
        for passed, reason in checks:
            if not passed:
                return False, reason
        return True, "ok"
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return False, f"lease_unavailable_{type(exc).__name__}"


def has_health_lease() -> bool:
    return health_lease_status()[0]


def acquire_run_lock(lock_path: Path) -> bool:
    """Acquire and retain an OS advisory lock for this process."""
    key = str(lock_path.expanduser().absolute())
    if key in _LOCKS:
        return True
    if not _safe_owned_path(lock_path.parent):
        return False
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCKS[key] = handle
        return True
    except (OSError, BlockingIOError):
        return False


def _check(
    config_path: str | None,
    repaired: set[str],
    *,
    inherited_singleton: Path | None = None,
) -> tuple[dict[str, Any], Any | None]:
    try:
        cfg = load_config(config_path)
    except Exception as exc:
        finding = _finding("config", False, type(exc).__name__)
        return {"ok": False, "carrier_ok": False, "integrity_ok": False, "findings": [finding]}, None

    from lokay.preflight_checks import (
        check_config,
        check_executor_availability,
        check_github_authentication,
        check_repository_catalog_clones,
        check_required_environment,
    )

    findings: list[dict[str, Any]] = []
    findings.append(check_required_environment(repaired=repaired))
    findings.append(check_config(cfg=cfg))
    # A missing managed checkout blocks worktree operations for that repository,
    # not GitHub-only triage or work in every other repository.  Status reports
    # the actionable clone inventory; global preflight must not deadlock the
    # mill before `lokay-repos-clone-missing` can repair it.
    findings.append(check_repository_catalog_clones(cfg=cfg))

    runtime_dirs = (cfg.state_path.parent, cfg.worktrees_root, Path(os.environ.get("LOKAY_LOG_DIR", str(Path.home() / ".lokay" / "logs"))))
    paths_ok = all(_safe_owned_path(path) and path.is_dir() and os.access(path, os.W_OK) for path in runtime_dirs)
    findings.append(_finding("writable_runtime_paths", paths_ok, "ok" if paths_ok else "unsafe_or_unwritable", repaired="directories" in repaired))
    try:
        free = min(shutil.disk_usage(path).free for path in runtime_dirs) / 1024**3
        disk_ok = free >= cfg.min_free_gb
    except OSError:
        disk_ok = False
    findings.append(_finding("disk_headroom", disk_ok, "ok" if disk_ok else "insufficient"))

    fala_ok, fala_code = _fala_smoke()
    findings.append(_finding("fala_smoke", fala_ok, fala_code))

    findings.append(check_github_authentication())
    git_ok, git_code = _github_git_transport(cfg)
    findings.append(
        _finding(
            "github_git_transport",
            git_ok,
            git_code,
            repaired="github_git_transport" in repaired,
        )
    )
    findings.append(check_executor_availability(cfg=cfg, repaired=repaired))

    lock_path = (cfg.state_path.parent / "mill.lock").expanduser().absolute()
    singleton_ok = inherited_singleton == lock_path or acquire_run_lock(lock_path)
    findings.append(_finding("singleton_overlap", singleton_ok, "ok" if singleton_ok else "contended"))

    # Manifest provenance is a carrier prerequisite: never run Fala from an
    # env-selected or mismatched graph.  Deeper Python syntax integrity remains
    # repairable once that trusted carrier is healthy.
    try:
        trusted_fala_manifest(); manifest_ok = True
    except (OSError, RuntimeError):
        manifest_ok = False
    findings.append(_finding("fala_manifest_provenance", manifest_ok, "ok" if manifest_ok else "untrusted_or_mismatch"))
    try:
        import ast
        integrity_ok = all(ast.parse(path.read_text(encoding="utf-8")) is not None for path in Path(__file__).parent.rglob("*.py"))
    except (OSError, SyntaxError, UnicodeError):
        integrity_ok = False
    findings.append(_finding("lokay_integrity", integrity_ok, "ok" if integrity_ok else "python_syntax_invalid"))
    carrier = [x for x in findings if x["name"] != "lokay_integrity"]
    return {"ok": all(x["ok"] for x in findings), "carrier_ok": all(x["ok"] for x in carrier), "integrity_ok": integrity_ok, "findings": findings}, cfg


def _incident_repo(cfg: Any | None) -> str:
    raw = getattr(cfg, "incident_repo", None) if cfg is not None else None
    repo = str(raw or _DEFAULT_INCIDENT_REPO).strip()
    return repo if "/" in repo else _DEFAULT_INCIDENT_REPO


def _incident_cooldown_hours(cfg: Any | None) -> float:
    raw = getattr(cfg, "incident_cooldown_hours", None) if cfg is not None else None
    try:
        hours = float(raw if raw is not None else _DEFAULT_INCIDENT_COOLDOWN_HOURS)
    except (TypeError, ValueError):
        hours = _DEFAULT_INCIDENT_COOLDOWN_HOURS
    return max(0.0, min(hours, 24.0 * 7))


def _incident_ledger_path(cfg: Any | None) -> Path:
    base = (
        cfg.state_path.parent
        if cfg is not None and _safe_owned_path(cfg.state_path.parent)
        else Path.home() / ".lokay"
    )
    if not _safe_owned_path(base):
        base = Path("/tmp") / f"lokay-{os.getuid()}"
    base.mkdir(parents=True, exist_ok=True)
    return base / "preflight-incidents.json"


def _read_incident_ledger(cfg: Any | None) -> dict[str, Any]:
    path = _incident_ledger_path(cfg)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return loaded
    except (OSError, ValueError):
        pass
    return {}


def reconcile_incident_ledger(cfg: Any | None = None) -> dict[str, Any]:
    """Mark local incident rows closed when the GitHub issue is closed."""
    ledger = _read_incident_ledger(cfg)
    closed = 0
    for entry in ledger.values():
        if not isinstance(entry, dict) or entry.get("state") != "open":
            continue
        repo = str(entry.get("repo") or "")
        number = entry.get("number")
        if not repo or number is None:
            continue
        viewed = subprocess.run(
            ["gh", "issue", "view", str(int(number)), "--repo", repo, "--json", "state"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if viewed.returncode != 0:
            continue
        try:
            state = str(json.loads(viewed.stdout or "{}").get("state") or "").upper()
        except ValueError:
            continue
        if state == "CLOSED":
            entry["state"] = "closed"
            closed += 1
    if closed:
        _write_incident_ledger(cfg, ledger)
    return {"ok": True, "closed": closed, "rows": len(ledger)}


def _write_incident_ledger(cfg: Any | None, data: dict[str, Any]) -> Path:
    path = _incident_ledger_path(cfg)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True)[:16384], encoding="utf-8")
    tmp.replace(path)
    return path


def _within_cooldown(entry: dict[str, Any], *, hours: float, now: float) -> bool:
    if hours <= 0:
        return False
    stamp = entry.get("last_incident_at", entry.get("created_at"))
    try:
        last = float(stamp)
    except (TypeError, ValueError):
        return False
    return (now - last) < (hours * 3600.0)


def _issue_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{int(number)}"


def _parse_issue_number(url: str) -> int | None:
    match = _ISSUE_NUMBER_RE.search(str(url or ""))
    return int(match.group(1)) if match else None


def incident_stamp_path(cfg: Any | None) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None) if cfg is not None else None
    if not path:
        return None
    return Path(path).expanduser().parent / INCIDENT_STAMP_NAME


def mill_incident_stamp_path() -> Path:
    """Operator mill leftover-incident stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / INCIDENT_STAMP_NAME


def _is_operator_mill_incident_stamp(stamp: Path) -> bool:
    mill = mill_incident_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def incident_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover-incident GitHub lists using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_incident_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = INCIDENT_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit


def _touch_incident_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_incident_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def _list_open_incidents(repo: str) -> list[dict[str, Any]] | None:
    """Open issues for the mill repo. None means the GitHub probe failed."""
    listed = subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "GET",
            "--paginate",
            f"repos/{repo}/issues",
            "-f",
            "state=open",
            "-f",
            "per_page=100",
            "--slurp",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    raw = getattr(listed, "stdout", "") or ""
    if listed.returncode != 0 or not raw.strip():
        return None
    try:
        pages = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(pages, list):
        return None
    return [
        row
        for page in pages
        if isinstance(page, list)
        for row in page
        if isinstance(row, dict) and "pull_request" not in row
    ]


def _close_resolved_incidents(repo: str, cfg: Any | None = None) -> dict[str, Any]:
    """Close leftover preflight tickets after the mill is healthy."""
    name = str(repo or "").strip()
    if not name:
        return {"ok": True, "closed": []}
    stamp = incident_stamp_path(cfg)
    # Idle leftover-incident skip outlives leftover-probe.
    # Hosted factory_pass stays at 300s. Leftover-probe host still lists when stamp is missing.
    idle_ttl = (
        IDLE_INCIDENT_TTL_SECONDS
        if os.environ.get("LOKAY_LEFTOVER_PROBE_GH_OK") == "1"
        else None
    )
    if incident_recently_empty(stamp, ttl=idle_ttl):
        return {"ok": True, "closed": [], "skipped": True, "reason": "recent_empty"}
    try:
        from lokay.triage import is_preflight_incident
    except ImportError:
        return {"ok": True, "closed": []}
    rows = _list_open_incidents(name)
    if rows is None:
        return {"ok": True, "closed": []}
    closed: list[int] = []
    for row in rows:
        number = row.get("number")
        try:
            issue_n = int(number)
        except (TypeError, ValueError):
            continue
        if not is_preflight_incident(
            title=str(row.get("title") or ""),
            body=str(row.get("body") or ""),
        ):
            continue
        done = subprocess.run(
            [
                "gh",
                "issue",
                "close",
                str(issue_n),
                "--repo",
                name,
                "--comment",
                "Preflight recovered; mill is healthy.",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        if done.returncode == 0:
            closed.append(issue_n)
    if closed:
        _clear_incident_stamp(stamp)
    else:
        _touch_incident_stamp(stamp)
    return {"ok": True, "closed": closed}


def _reopen_issue(repo: str, number: int, summary: str) -> bool:
    reopened = subprocess.run(
        ["gh", "issue", "reopen", str(number), "--repo", repo],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    if reopened.returncode != 0:
        # Already open is fine; continue to comment.
        view = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", repo, "--json", "state"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if view.returncode != 0:
            return False
        try:
            state = str(json.loads(view.stdout or "{}").get("state") or "").upper()
        except ValueError:
            return False
        if state != "OPEN":
            return False
    commented = subprocess.run(
        [
            "gh",
            "issue",
            "comment",
            str(number),
            "--repo",
            repo,
            "--body",
            f"Preflight failed again: {summary}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    return commented.returncode == 0


def _persist_incident(cfg: Any | None, result: dict[str, Any]) -> Path:
    data = _read_incident_ledger(cfg)
    fp = result["fingerprint"]
    prev = dict(data.get(fp) or {}) if isinstance(data.get(fp), dict) else {}
    prev.update(
        {
            "fingerprint": fp,
            "failed": [x["name"] for x in result["findings"] if not x["ok"]],
        }
    )
    data[fp] = prev
    return _write_incident_ledger(cfg, data)


def _github_incident(result: dict[str, Any], cfg: Any | None = None) -> str | None:
    """Create or reuse the deduplicated Lokay recovery incident (cooldown-aware)."""
    failed = [x for x in result["findings"] if not x["ok"]]
    # Lock contention, missing clones, and unusable host runtime directories
    # are operational inventory, not source defects. Keep this guard at the
    # mutation boundary so a config/permission problem (or a bounded probe
    # using an intentionally unsafe path) cannot create recursive source work.
    non_source_failures = {
        "repository_catalog_clones",
        "singleton_overlap",
        "writable_runtime_paths",
        "disk_headroom",
    }
    if failed and {item["name"] for item in failed} <= non_source_failures:
        return None
    if not any(x["name"] == "github_authentication" and x["ok"] for x in result["findings"]):
        return None
    fp = str(result["fingerprint"])
    marker = f"<!-- lokay-preflight:{fp} -->"
    repo = _incident_repo(cfg)
    cooldown_h = _incident_cooldown_hours(cfg)
    now = time.time()
    ledger = _read_incident_ledger(cfg)
    entry = dict(ledger.get(fp) or {}) if isinstance(ledger.get(fp), dict) else {}
    summary = str(result.get("incident_summary") or "") or ", ".join(
        x["name"] for x in result["findings"] if not x["ok"]
    )
    try:
        rows = _list_open_incidents(repo)
        if rows is None:
            return None
        match = next((r for r in rows if marker in str(r.get("body") or "")), None)
        if match:
            number = int(match["number"])
            url = _issue_url(repo, number)
            if not _within_cooldown(entry, hours=cooldown_h, now=now):
                commented = subprocess.run(
                    [
                        "gh",
                        "issue",
                        "comment",
                        str(number),
                        "--repo",
                        repo,
                        "--body",
                        f"Preflight failed again: {summary}",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
                if commented.returncode != 0:
                    return None
                entry["last_incident_at"] = now
            entry.update(
                {
                    "fingerprint": fp,
                    "incident_url": url,
                    "number": number,
                    "repo": repo,
                    "state": "open",
                }
            )
            if "created_at" not in entry:
                entry["created_at"] = now
            ledger[fp] = entry
            _write_incident_ledger(cfg, ledger)
            _clear_incident_stamp(incident_stamp_path(cfg))
            return url

        cached_url = str(entry.get("incident_url") or "")
        cached_number = entry.get("number")
        if cached_number is None and cached_url:
            cached_number = _parse_issue_number(cached_url)
        # Skip create/comment while cooldown holds for this fingerprint.
        if cached_url and _within_cooldown(entry, hours=cooldown_h, now=now):
            return cached_url[:240]

        if cached_number is not None and _reopen_issue(
            repo, int(cached_number), summary
        ):
            url = _issue_url(repo, int(cached_number))
            entry.update(
                {
                    "fingerprint": fp,
                    "incident_url": url,
                    "number": int(cached_number),
                    "repo": repo,
                    "state": "open",
                    "last_incident_at": now,
                }
            )
            if "created_at" not in entry:
                entry["created_at"] = now
            ledger[fp] = entry
            _write_incident_ledger(cfg, ledger)
            _clear_incident_stamp(incident_stamp_path(cfg))
            return url

        made = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                f"Preflight failure {fp}",
                "--body",
                f"{marker}\nBounded checks failed: {summary}",
                "--label",
                "ai:blocked",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if made.returncode != 0:
            return None
        url = getattr(made, "stdout", "").strip()[:240]
        if not url:
            return None
        number = _parse_issue_number(url)
        entry.update(
            {
                "fingerprint": fp,
                "incident_url": url,
                "number": number,
                "repo": repo,
                "state": "open",
                "created_at": now,
                "last_incident_at": now,
                "failed": [x["name"] for x in result["findings"] if not x["ok"]],
            }
        )
        ledger[fp] = entry
        _write_incident_ledger(cfg, ledger)
        _clear_incident_stamp(incident_stamp_path(cfg))
        return url
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def report_recovery_incident(
    *,
    fingerprint: str,
    evidence: str,
    config_path: str | None = None,
) -> str | None:
    """Report a confirmed product stall through the same deduplicated lane."""
    cfg = None
    if config_path:
        try:
            cfg = load_config(config_path)
        except Exception:
            cfg = None
    return _github_incident(
        {
            "fingerprint": fingerprint,
            "incident_summary": (
                "Confirmed in 4 of 5 daemon runs. Repeated product failure evidence:\n\n"
                + evidence[:6000]
            ),
            "findings": [
                {"name": "github_authentication", "ok": True},
                {"name": "confirmed_product_stall", "ok": False},
            ],
        },
        cfg=cfg,
    )


def run_preflight(
    config_path: str | None,
    *,
    remediate: bool = True,
    issue_lease: bool = False,
    validate_inherited_lease: bool = False,
) -> dict[str, Any]:
    inherited_lease = os.environ.get("LOKAY_HEALTH_LEASE", "")
    inherited_singleton: Path | None = None
    if inherited_lease:
        expected_lock: Path | None = None
        if validate_inherited_lease:
            try:
                expected_lock = load_config(config_path).state_path.parent / "mill.lock"
            except Exception:
                expected_lock = None
        healthy, reason = (
            health_lease_status(lock_path=expected_lock)
            if expected_lock is not None
            else health_lease_status()
        )
        if not healthy:
            return {
                "ok": False,
                "carrier_ok": False,
                "integrity_ok": False,
                "health": "preflight_failed",
                "gate_released": False,
                "lease": False,
                "lease_reason": reason,
                "findings": [],
                "repairs": [],
            }
        if not validate_inherited_lease:
            return {
                "ok": True,
                "carrier_ok": True,
                "integrity_ok": True,
                "health": "healthy",
                "gate_released": True,
                "lease": True,
                "lease_reason": "ok",
                "findings": [],
                "repairs": [],
            }
        if expected_lock is not None:
            # Self-repair validation reruns host checks while bypassing only
            # the exact configured lock proven by the inherited lease.
            inherited_singleton = expected_lock.expanduser().absolute()
    repaired: set[str] = set()
    repairs: list[dict[str, Any]] = []
    initial, cfg = _check(
        config_path, repaired, inherited_singleton=inherited_singleton
    )
    if remediate:
        if any(x["name"] == "required_environment" and not x["ok"] for x in initial["findings"]) and not os.environ.get("LANG"):
            os.environ["LANG"] = "C.UTF-8"; repaired.add("locale")
            repairs.append({"kind": "set_process_locale", "ok": True, "value": _REDACTED})
        if cfg is not None:
            dirs = (cfg.state_path.parent, cfg.worktrees_root, Path(os.environ.get("LOKAY_LOG_DIR", str(Path.home() / ".lokay" / "logs"))))
            if all(_safe_owned_path(path) for path in dirs):
                try:
                    for path in dirs: path.mkdir(parents=True, exist_ok=True)
                    repaired.add("directories"); repairs.append({"kind": "create_runtime_directories", "ok": True})
                except OSError:
                    repairs.append({"kind": "create_runtime_directories", "ok": False})
            if any(
                x["name"] == "github_git_transport" and not x["ok"]
                for x in initial["findings"]
            ) and _repair_github_git_transport(cfg):
                repaired.add("github_git_transport")
                repairs.append({"kind": "set_canonical_github_ssh_origins", "ok": True})
            if cfg.live and cfg.executor_enabled and _repair_runtime_path(cfg.agent_command):
                repaired.add("executor_path")
                repairs.append({"kind": "extend_runtime_path", "ok": True})
    if initial.get("ok"):
        # First host check already healthy. A second pass would only
        # re-hit GitHub /user and re-parse every lokay module.
        checked = initial
    else:
        checked, cfg = _check(
            config_path, repaired, inherited_singleton=inherited_singleton
        )
    failed = sorted(f"{x['name']}:{x['code']}" for x in checked["findings"] if not x["ok"])
    fp = hashlib.sha256("\n".join(failed).encode()).hexdigest()[:16]
    failed_findings = [x for x in checked["findings"] if not x["ok"]]
    operational_names = {"repository_catalog_clones", "singleton_overlap"}
    operational_overlap = (
        any(
            item["name"] == "singleton_overlap" and item["code"] == "contended"
            for item in failed_findings
        )
        and {item["name"] for item in failed_findings} <= operational_names
    )
    # Contention means another healthy invocation owns the run slot. It still
    # fails closed, but is an operational outcome rather than broken preflight
    # health and must never enter the source-repair lane. Accept the legacy
    # missing-clone finding here so an upgrading daemon cannot report #30 again.
    health = "overlap" if operational_overlap else ("healthy" if checked["ok"] else "preflight_failed")
    result = {**checked, "health": health, "fingerprint": fp, "gate_released": checked["ok"], "repairs": repairs}
    if operational_overlap:
        result["operational_overlap"] = True
    if checked["ok"] and issue_lease:
        issue_health_lease(lock_path=cfg.state_path.parent / "mill.lock")
        try:
            result["resolved_incidents"] = _close_resolved_incidents(
                _incident_repo(cfg), cfg
            )
        except OSError:
            result["resolved_incidents"] = {"ok": False, "closed": []}
    if not checked["ok"]:
        if operational_overlap:
            # Overlap is already represented by the structured result. Do not
            # put it in either incident channel, where a consumer could mistake
            # expected scheduler contention for a source-repair task.
            result.update(local_incident=None, incident_url=None)
        else:
            try: result["local_incident"] = str(_persist_incident(cfg, result))
            except OSError: result["local_incident"] = None
            result["incident_url"] = _github_incident(result, cfg=cfg)
    return result


def require_healthy(config_path: str | None) -> None:
    healthy, lease_reason = health_lease_status()
    if healthy:
        return
    # Inherited token + missing file: restore the record (same token) so a live
    # mill can keep mutating. Other rejected leases stay fail-closed.
    restorable = (
        str(lease_reason).startswith("lease_unavailable_FileNotFound")
        or str(lease_reason).startswith("lease_unavailable_ProcessLookup")
        or str(lease_reason) == "lock_not_held"
    )
    if os.environ.get("LOKAY_HEALTH_LEASE") and restorable:
        try:
            issue_health_lease()
        except RuntimeError:
            pass
        healthy, lease_reason = health_lease_status()
        if healthy:
            return
    # An inherited token is a capability, not a request to mint another one.
    # If its backing record/lock cannot be validated, fail closed immediately;
    # a nested atom must never overwrite the daemon's process-tree lease.
    if os.environ.get("LOKAY_HEALTH_LEASE"):
        raise RuntimeError(
            f"preflight failed; live mutation blocked (lease={lease_reason})"
        )
    result = run_preflight(config_path, remediate=True)
    if not result["ok"]:
        raise RuntimeError(
            f"preflight failed; live mutation blocked (lease={lease_reason})"
        )
