#!/usr/bin/env bash
# Continuous Lokay mill — one pass, invoked by launchd.
# mill_scope=mikolaj92/lokay (this host). Catalog yaml is not the delivery set.
# Host LaunchAgent StartInterval is 60s (not 600). Plist stays on the host.
set -euo pipefail

# launchd should provide HOME; retain a per-uid bounded fallback when it does not.
HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export HOME
export PATH="${HOME}/.local/bin:${HOME}/.local/share/mise/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export LANG="${LANG:-C.UTF-8}"
export TMPDIR="${TMPDIR:-/tmp}"

export LOKAY_ROOT="${LOKAY_ROOT:-${HOME}/Developer/OSS/lokay}"
export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
ROOT="${LOKAY_ROOT}"
export LOKAY_CONFIG="${LOKAY_CONFIG:-${ROOT}/config.yaml}"
CFG="${LOKAY_CONFIG}"
LOKAY_HOME="${HOME}/.lokay"
LOG_DIR="${LOKAY_LOG_DIR:-${LOKAY_HOME}/logs}"
OUTBOX="${LOKAY_HOME}/preflight-bootstrap-incidents.log"
LOKAY_LAUNCHD_LABEL="${LOKAY_LAUNCHD_LABEL:-ai.mikolaj.lokay-mill}"
# Fail-closed operator interval: 60s heartbeat, never the old 600s tick.
LOKAY_LAUNCHD_START_INTERVAL=60
LOKAY_LAUNCHD_PLIST="${LOKAY_LAUNCHD_PLIST:-${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist}"
LOKAY_MILL_LOCK="${LOKAY_MILL_LOCK:-${LOKAY_HOME}/mill.lock}"
LOKAY_KEEPALIVE_STAMP="${LOKAY_KEEPALIVE_STAMP:-${LOKAY_HOME}/launchd-keepalive.stamp}"

_python() {
  if command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  elif [[ -x /usr/bin/python3 ]]; then
    /usr/bin/python3 "$@"
  else
    return 127
  fi
}

bootstrap_incident() {
  # Bound bootstrap evidence even when Python/package/config cannot start.
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

write_host_plist_interval() {
  # Plist is host-only. Write 60s + crash KeepAlive; do not invent a job.
  local plist="$1"
  local want="$2"
  [[ -f "${plist}" ]] || return 0
  _python - "${plist}" "${want}" <<'PY'
import plistlib, sys

path, want = sys.argv[1], int(sys.argv[2])
with open(path, "rb") as handle:
    data = plistlib.load(handle)
want_keep = {"SuccessfulExit": False}
if data.get("StartInterval") == want and data.get("KeepAlive") == want_keep:
    raise SystemExit(0)
data["StartInterval"] = want
data["KeepAlive"] = want_keep
with open(path, "wb") as handle:
    plistlib.dump(data, handle, fmt=plistlib.FMT_XML)
PY
}

host_ff_updated() {
  # Last host-ff envelope in this tick. True when ff-only moved HEAD.
  local log="${1:-${LOG:-}}"
  [[ -n "${log}" && -f "${log}" ]] || return 1
  _python - "${log}" <<'PY'
import json, sys
from pathlib import Path

updated = False
try:
    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
except OSError:
    raise SystemExit(1)
for line in text.splitlines():
    raw = line.strip()
    if "{" not in raw:
        continue
    try:
        parsed = json.loads(raw)
    except ValueError:
        continue
    if isinstance(parsed, dict) and "updated" in parsed:
        updated = bool(parsed.get("updated"))
raise SystemExit(0 if updated else 1)
PY
}

mill_lock_busy() {
  # Singleton lock stays: a parallel tick must not start a second mill,
  # and a busy lock means the caretaker must not reload launchd.
  local lock="${LOKAY_MILL_LOCK}"
  [[ -e "${lock}" ]] || return 1
  _python - "${lock}" <<'PY'
import fcntl, sys

path = sys.argv[1]
try:
    handle = open(path, "a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

host_ff_already_current() {
  # 0 = GitHub main already matches HEAD and origin/main. Probe failure hosts.
  # Fresh idle stamps skip the GitHub SHA probe. Busy lock still probes.
  local checkout="${1:-${ROOT}}"
  local lock_busy="${2:-0}"
  _python - "${checkout}" "${lock_busy}" \
    "${LOKAY_HOME}/last-pass.json" \
    "${LOKAY_HOME}/factory-survey.stamp" \
    "${LOKAY_HOME}/leftover-closeout.stamp" <<'PY'
import json, os, re, subprocess, sys, time
from pathlib import Path

checkout = Path(sys.argv[1])
lock_busy = sys.argv[2]
receipt_path, survey_stamp, leftover_stamp = sys.argv[3:6]
csi = re.compile("\x1b\[[0-9;]*[mK]")

def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()

head = git("rev-parse", "HEAD")
remote = git("rev-parse", "origin/main")
branch = git("rev-parse", "--abbrev-ref", "HEAD")
origin = git("remote", "get-url", "origin").removesuffix(".git")
if (
    not head
    or not remote
    or head != remote
    or branch != "main"
    or origin
    not in {
        "https://github.com/mikolaj92/lokay",
        "git@github.com:mikolaj92/lokay",
        "ssh://git@github.com/mikolaj92/lokay",
    }
):
    raise SystemExit(1)

def emit() -> None:
    print(
        json.dumps(
            {
                "ok": True,
                "planned": False,
                "checkout": str(checkout),
                "health": "current",
                "updated": False,
                "already_current": True,
                "head": head,
                "origin_main": remote,
            }
        )
    )

if lock_busy != "1":
    now = time.time()

    def age_of(path: str):
        try:
            return now - Path(path).stat().st_mtime
        except OSError:
            return None

    leftover_age = age_of(leftover_stamp)
    survey_age = age_of(survey_stamp)
    idle = False
    try:
        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        remaining = receipt.get("remaining") if isinstance(receipt, dict) else None
        if isinstance(remaining, dict) and (
            receipt.get("health") == "idle" or receipt.get("idle")
        ):
            work = (
                int(remaining.get("inbox") or 0)
                + int(remaining.get("ready") or 0)
                + int(remaining.get("open_ai_prs") or 0)
                + int(remaining.get("issue_to_pr_started") or 0)
                + int(remaining.get("survey_errors") or 0)
            )
            by_repo = remaining.get("by_repo") or receipt.get("by_repo") or []
            occupied = isinstance(by_repo, list) and any(
                isinstance(row, dict) and bool(row.get("occupied")) for row in by_repo
            )
            idle = work == 0 and not occupied
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        idle = False
    if (
        idle
        and leftover_age is not None
        and 0 <= leftover_age < 300
        and survey_age is not None
        and 0 <= survey_age < 120
    ):
        emit()
        raise SystemExit(0)

env = os.environ.copy()
env["GH_NO_COLOR"] = "1"
env["NO_COLOR"] = "1"
try:
    result = subprocess.run(
        [
            "gh",
            "api",
            "repos/mikolaj92/lokay/git/ref/heads/main",
            "--jq",
            ".object.sha",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
except (OSError, subprocess.TimeoutExpired):
    raise SystemExit(1)
if result.returncode != 0:
    raise SystemExit(1)
sha = csi.sub("", result.stdout or "").strip()
if not sha or sha != head:
    raise SystemExit(1)
emit()
PY
}

idle_skip_daemon() {
  # 0 + reason on stdout = skip lokay-daemon. Missing leftover stamp,
  # occupied last-pass, remaining work, or a failed GitHub probe hosts.
  _python - \
    "${LOKAY_HOME}/last-pass.json" \
    "${LOKAY_HOME}/factory-survey.stamp" \
    "${LOKAY_HOME}/leftover-closeout.stamp" <<'PY'
import json, os, re, subprocess, sys, time
from pathlib import Path

receipt_path, survey_stamp, leftover_stamp = sys.argv[1:4]
now = time.time()
csi = re.compile("\x1b\\[[0-9;]*[mK]")
decided = {
    "ai:ready", "ai:blocked", "ai:needs-feedback", "work:ready",
    "frozen", "ai:frozen", "ai:tracker",
    "ai:in-progress", "ai:pr-open", "ai:ci-waiting", "ai:repairing",
}

def age_of(path):
    try:
        return now - Path(path).stat().st_mtime
    except OSError:
        return None

def fresh(path: str, ttl: int) -> bool:
    age = age_of(path)
    return age is not None and 0 <= age < ttl

try:
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    raise SystemExit(1)
if not isinstance(receipt, dict):
    raise SystemExit(1)
if receipt.get("health") != "idle" and not receipt.get("idle"):
    raise SystemExit(1)
remaining = receipt.get("remaining")
if not isinstance(remaining, dict):
    raise SystemExit(1)
work = (
    int(remaining.get("inbox") or 0)
    + int(remaining.get("ready") or 0)
    + int(remaining.get("open_ai_prs") or 0)
    + int(remaining.get("issue_to_pr_started") or 0)
    + int(remaining.get("survey_errors") or 0)
)
if work:
    raise SystemExit(1)
by_repo = remaining.get("by_repo") or receipt.get("by_repo") or []
if isinstance(by_repo, list) and any(
    isinstance(row, dict) and bool(row.get("occupied")) for row in by_repo
):
    raise SystemExit(1)
leftover_age = age_of(leftover_stamp)
if leftover_age is None:
    raise SystemExit(1)
survey_age = age_of(survey_stamp)
if survey_age is None:
    raise SystemExit(1)

def gh_list(args, cap=1000):
    env = os.environ.copy()
    env["GH_NO_COLOR"] = "1"
    env["NO_COLOR"] = "1"
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(csi.sub("", result.stdout or "[]"))
    except ValueError:
        return None
    if not isinstance(rows, list) or len(rows) >= cap:
        return None
    return rows

def closed_ready(rows):
    if rows is None:
        return None
    return any(
        isinstance(row, dict)
        and str(row.get("state") or "").upper() == "CLOSED"
        and int(row.get("number") or 0) > 0
        for row in rows
    )

repo = os.environ.get("LOKAY_MILL_REPO", "").strip() or "mikolaj92/lokay"
leftover_probed = False
if leftover_age >= 300:
    work_ready = gh_list(
        ["issue", "list", "--repo", repo, "--state", "closed", "--label", "work:ready", "--json", "number,state", "--limit", "100"],
        cap=100,
    )
    ai_ready = gh_list(
        ["issue", "list", "--repo", repo, "--state", "closed", "--label", "ai:ready", "--json", "number,state", "--limit", "100"],
        cap=100,
    )
    leftover_work = closed_ready(work_ready)
    leftover_ai = closed_ready(ai_ready)
    if leftover_work is None or leftover_ai is None or leftover_work or leftover_ai:
        raise SystemExit(1)
    try:
        Path(leftover_stamp).write_text(str(int(now)), encoding="utf-8")
    except OSError:
        pass
    leftover_probed = True

if 0 <= survey_age < 120:
    print("recent_empty_leftover_probe" if leftover_probed else "recent_empty_survey")
    raise SystemExit(0)

prs = gh_list(["pr", "list", "--repo", repo, "--state", "open", "--json", "headRefName", "--limit", "1000"])
if prs is None:
    raise SystemExit(1)
if any(str(row.get("headRefName") or "").startswith("ai/fix/") for row in prs if isinstance(row, dict)):
    raise SystemExit(1)
ready = gh_list(["issue", "list", "--repo", repo, "--state", "open", "--label", "work:ready", "--json", "number,state", "--limit", "1000"])
if ready is None:
    raise SystemExit(1)
if any(isinstance(row, dict) and str(row.get("state") or "").upper() != "CLOSED" and int(row.get("number") or 0) > 0 for row in ready):
    raise SystemExit(1)
inbox = gh_list(["issue", "list", "--repo", repo, "--state", "open", "--json", "labels", "--limit", "1000"])
if inbox is None:
    raise SystemExit(1)
for row in inbox:
    if not isinstance(row, dict):
        continue
    names = set()
    raw = row.get("labels")
    if isinstance(raw, list):
        for item in raw:
            name = str(item.get("name") or "") if isinstance(item, dict) else str(item or "")
            if name:
                names.add(name)
    if not (names & decided):
        raise SystemExit(1)
try:
    Path(survey_stamp).write_text(str(int(now)), encoding="utf-8")
except OSError:
    pass
print("recent_empty_survey_probe")
raise SystemExit(0)
PY
}

loaded_start_interval() {
  local label="$1"
  local uid
  uid="$(id -u)"
  command -v launchctl >/dev/null 2>&1 || return 0
  launchctl print "user/${uid}/${label}" 2>/dev/null | awk '/run interval/ {print $4; exit}'
}

loaded_plist_path() {
  # First "path =" is the loaded job definition. A vanished tmp plist
  # (pytest / leftover bootstrap) still prints as healthy 60s.
  local label="$1"
  local uid
  uid="$(id -u)"
  command -v launchctl >/dev/null 2>&1 || return 0
  launchctl print "user/${uid}/${label}" 2>/dev/null | awk '/^[[:space:]]*path = / {print $3; exit}'
}

loaded_keepalive_crash_only() {
  # 0 when the loaded job restarts on unsuccessful exit, not on idle 0.
  local label="$1"
  local uid text
  uid="$(id -u)"
  command -v launchctl >/dev/null 2>&1 || return 1
  text="$(launchctl print "user/${uid}/${label}" 2>/dev/null || true)"
  [[ -n "${text}" ]] || return 1
  printf '%s' "${text}" | _python - <<'PY'
import sys

text = sys.stdin.read().lower()
if "keep alive" not in text and "keepalive" not in text:
    raise SystemExit(1)
compact = "".join(text.split())
if (
    "successfulexit=>false" in compact
    or "successfulexit=>0" in compact
    or "successfulexit=false" in compact
    or "successfulexit=0" in compact
):
    raise SystemExit(0)
raise SystemExit(1)
PY
}

reload_launchagent() {
  local plist="$1"
  local label="$2"
  local uid domain
  uid="$(id -u)"
  domain="user/${uid}"
  launchctl bootout "${domain}/${label}" >/dev/null 2>&1 || true
  launchctl bootstrap "${domain}" "${plist}" >/dev/null 2>&1 || true
}

caretaker_write_interval() {
  local plist="${LOKAY_LAUNCHD_PLIST}"
  local want="${LOKAY_LAUNCHD_START_INTERVAL}"
  [[ -f "${plist}" ]] || return 0
  write_host_plist_interval "${plist}" "${want}" || true
}

caretaker_reload_if_idle() {
  # Load the host plist only after idle. Never launchctl while mill.lock
  # is held (lokay is still in a cycle). pytest HOME is not the host.
  local plist="${LOKAY_LAUNCHD_PLIST}"
  local label="${LOKAY_LAUNCHD_LABEL}"
  local want="${LOKAY_LAUNCHD_START_INTERVAL}"
  local loaded=""
  local loaded_path=""
  [[ -f "${plist}" ]] || return 0
  [[ "${HOME}" == /Users/* ]] || return 0
  [[ "${plist}" == "${HOME}/Library/LaunchAgents/${label}.plist" ]] || return 0
  command -v launchctl >/dev/null 2>&1 || return 0
  loaded="$(loaded_start_interval "${label}")"
  loaded_path="$(loaded_plist_path "${label}")"
  if [[ "${loaded}" == "${want}" && -n "${loaded_path}" && -f "${loaded_path}" ]] && loaded_keepalive_crash_only "${label}"; then
    return 0
  fi
  if mill_lock_busy; then
    return 0
  fi
  reload_launchagent "${plist}" "${label}"
}

if [[ "${1:-}" == "--install" ]]; then
  mkdir -p "${LOKAY_HOME}" || exit 70
  caretaker_write_interval
  caretaker_reload_if_idle
  if ! mill_lock_busy; then
    : > "${LOKAY_KEEPALIVE_STAMP}" || true
  fi
  exit 0
fi

# Bootstrap precedes uv/package/config/log dependencies and persists bounded failures.
mkdir -p "${LOKAY_HOME}" || exit 70
if ! mkdir -p "${LOG_DIR}"; then
  bootstrap_incident "log_directory"
  exit 73
fi
if ! command -v uv >/dev/null 2>&1; then
  bootstrap_incident "uv_unavailable"
  exit 69
fi
if [[ ! -d "${ROOT}" || ! -f "${CFG}" ]]; then
  bootstrap_incident "root_or_config"
  exit 66
fi

cd "${ROOT}"
export LOKAY_ROOT="${ROOT}"
# site-packages/lokay (hatch force-include wheel) shadows the editable pth.
# Organ subprocesses and detached i2pr must import the checkout, not a stale copy.
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

# Live factory (override with env in the plist if needed). This LaunchAgent
# runs the PR mill only; collector patches own their post-merge durable
# background startup. Never use this loop to populate collector data or wait.
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"
# Present for Fala inherit_env. After caretaker host-ff this becomes 1.
export LOKAY_HOST_FF_FETCHED="${LOKAY_HOST_FF_FETCHED:-}"
# merge.require_checks lives in config.yaml / LaunchAgent plist. Do not
# default 1 here: that would override local-trust YAML when the caretaker
# runs without a plist env.

if [[ -d "${HOME}/Developer/OSS/Fala/mojo/fala" ]]; then
  export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
fi

# Keep the on-disk host interval at 60s. Do not launchctl here — this process
# is the live cycle. Caretaker (--install) loads after idle when the lock is free.
caretaker_write_interval

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/mill-${STAMP}.log"
LATEST="${LOG_DIR}/mill-latest.log"
DIGEST_FILE="${LOKAY_UV_DIGEST:-${LOKAY_HOME}/uv-install.digest}"
# Bounded transcripts: launchd stdout stays a glance; mill-*.log keeps the body.
MILL_LOG_MAX="${LOKAY_MILL_LOG_MAX:-1048576}"
LAUNCHD_STDOUT_MAX="${LOKAY_LAUNCHD_STDOUT_MAX:-1048576}"
MILL_LOG_KEEP="${LOKAY_MILL_LOG_KEEP:-48}"

package_matches() {
  # 0 = site-packages matches src (or no copy to compare). 1 = stale wheel.
  _python - "${ROOT}" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = root / "src" / "lokay"
if not src.is_dir():
    raise SystemExit(0)
copies = list((root / ".venv").glob("lib/python*/site-packages/lokay"))
if not copies:
    raise SystemExit(0)
sp = copies[0]
for path in src.rglob("*.py"):
    if "__pycache__" in path.parts:
        continue
    other = sp / path.relative_to(src)
    try:
        if not other.is_file() or other.read_bytes() != path.read_bytes():
            raise SystemExit(1)
    except OSError:
        raise SystemExit(1)
raise SystemExit(0)
PY
}

checkout_digest() {
  _python - "${ROOT}" "${FALA_HOME:-}" <<'PY'
import hashlib, subprocess, sys
from pathlib import Path

def head(path: str) -> str:
    if not path:
        return ""
    repo = Path(path)
    git_dir = repo / ".git"
    if not repo.exists() or not (git_dir.exists() or git_dir.is_file()):
        return ""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unreadable"
    return (out.stdout or "").strip() or "unreadable"

parts = [f"lokay:{head(sys.argv[1])}", f"fala:{head(sys.argv[2])}"]
for rel in ("pyproject.toml", "uv.lock"):
    path = Path(sys.argv[1]) / rel
    try:
        stat = path.stat()
        parts.append(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}")
    except OSError:
        parts.append(f"{rel}:missing")
print(hashlib.sha256("\n".join(parts).encode()).hexdigest())
PY
}

bound_file() {
  # Stream head+tail in place. Never slurp a GiB launchd log into RAM,
  # and keep the same inode so an already-open stdout fd can be rebound.
  local path="$1"
  local max_bytes="$2"
  local size=""
  [[ -f "${path}" ]] || return 0
  # Small idle transcripts skip python. Fat logs still truncate in place.
  size="$(wc -c < "${path}" 2>/dev/null || true)"
  size="${size// /}"
  case "${max_bytes}" in
    ''|*[!0-9]*) ;;
    *)
      if [[ -n "${size}" && "${size}" -le "${max_bytes}" ]]; then
        return 0
      fi
      ;;
  esac
  _python - "${path}" "${max_bytes}" <<'PY'
import os, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    limit = int(sys.argv[2])
except ValueError:
    raise SystemExit(0)
if limit < 1024:
    raise SystemExit(0)
try:
    size = path.stat().st_size
except OSError:
    raise SystemExit(0)
if size <= limit:
    raise SystemExit(0)
head_n = max(256, limit // 4)
tail_n = max(256, limit - head_n - 32)
marker = b"\n... truncated ...\n"
try:
    fd = os.open(path, os.O_RDWR)
except OSError:
    raise SystemExit(0)
try:
    head = os.read(fd, head_n)
    os.lseek(fd, max(0, size - tail_n), os.SEEK_SET)
    tail = os.read(fd, tail_n)
    blob = head + marker + tail
    if not blob.endswith(b"\n"):
        blob += b"\n"
    os.lseek(fd, 0, os.SEEK_SET)
    written = os.write(fd, blob)
    os.ftruncate(fd, written)
    os.fsync(fd)
finally:
    os.close(fd)
PY
}

launchd_stdout_paths() {
  _python - "${LOKAY_LAUNCHD_PLIST}" "${LOKAY_HOME}" "${LOG_DIR}" <<'PY'
import plistlib, sys
from pathlib import Path

seen = []
def add(path: str) -> None:
    text = (path or "").strip()
    if text and text not in seen:
        seen.append(text)

plist = Path(sys.argv[1])
if plist.is_file():
    try:
        with plist.open("rb") as handle:
            data = plistlib.load(handle)
    except Exception:
        data = {}
    if isinstance(data, dict):
        add(str(data.get("StandardOutPath") or ""))
        add(str(data.get("StandardErrorPath") or ""))
add(str(Path(sys.argv[2]) / "launchd-stdout.log"))
add(str(Path(sys.argv[3]) / "launchd-stdout.log"))
print("\n".join(seen))
PY
}

prune_mill_logs() {
  _python - "${LOG_DIR}" "${MILL_LOG_KEEP}" <<'PY'
import sys
from pathlib import Path

log_dir = Path(sys.argv[1])
try:
    keep = max(1, int(sys.argv[2]))
except ValueError:
    keep = 48
try:
    logs = [
        path
        for path in log_dir.glob("mill-*.log")
        if path.name != "mill-latest.log"
    ]
except OSError:
    raise SystemExit(0)
logs.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
for stale in logs[keep:]:
    try:
        stale.unlink()
    except OSError:
        pass
PY
}

emit_launchd_glance() {
  # Head+tail only. Nested mill.health wins so a Fala ok:false wrapper still
  # reports progress on the glance line. A truncated one-line envelope
  # still yields health via regex or last-pass.json.
  _python - "${LOG}" "${LOKAY_HOME}/last-pass.json" <<'PY'
import json, re, sys
from pathlib import Path

def head_and_tail(path: Path, limit: int = 262144) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            head = handle.read(limit)
            if size > limit:
                handle.seek(max(limit, size - limit))
                tail = handle.read(limit)
            else:
                tail = b""
        return (head + tail).decode("utf-8", "replace")
    except OSError:
        return ""

def as_dict(value):
    return value if isinstance(value, dict) else None

def remaining_of(payload):
    remaining = payload.get("remaining")
    return remaining if isinstance(remaining, dict) else {}

def glance_of(payload):
    sources = [payload]
    mill = as_dict(payload.get("mill"))
    if mill is not None:
        sources.append(mill)
    last = as_dict(payload.get("last"))
    if last is not None:
        sources.append(last)
    terminal = as_dict(payload.get("terminal"))
    if terminal is not None:
        recovery_mill = as_dict(terminal.get("recovery_mill"))
        if recovery_mill is not None:
            nested = as_dict(recovery_mill.get("mill"))
            sources.append(nested if nested is not None else recovery_mill)
    for src in sources:
        health = str(src.get("health") or "")
        remaining = remaining_of(src)
        started = int(remaining.get("issue_to_pr_started") or 0)
        progress = int(src.get("progress") or 0)
        if health == "progress" or started > 0 or progress > 0:
            return {
                "ok": bool(src.get("ok")),
                "health": health or "progress",
                "progress": max(progress, started),
                "remaining": remaining,
                "error": src.get("error"),
            }
    return {
        "ok": bool(payload.get("ok")),
        "health": str(payload.get("health") or "unknown"),
        "progress": int(payload.get("progress") or 0),
        "remaining": remaining_of(payload),
        "error": payload.get("error"),
    }

def load_json(path: Path):
    try:
        parsed = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None

def scrape_truncated(text: str) -> dict:
    out = {}
    healths = re.findall(r'"health"\s*:\s*"([^"]+)"', text)
    if "progress" in healths:
        out["health"] = "progress"
    elif healths:
        out["health"] = healths[-1]
    progress = re.search(r'"progress"\s*:\s*(-?\d+)', text)
    if progress:
        out["progress"] = int(progress.group(1))
    started = re.search(r'"issue_to_pr_started"\s*:\s*(-?\d+)', text)
    if started:
        out["remaining"] = {"issue_to_pr_started": int(started.group(1))}
    ok_m = re.search(r'"ok"\s*:\s*(true|false)', text)
    if ok_m:
        out["ok"] = ok_m.group(1) == "true"
    return out

def productive(look):
    if str(look.get("health") or "") == "progress":
        return True
    if int(look.get("progress") or 0) > 0:
        return True
    remaining = look.get("remaining")
    return isinstance(remaining, dict) and int(remaining.get("issue_to_pr_started") or 0) > 0

text = head_and_tail(Path(sys.argv[1]))
candidates = []
for line in text.splitlines():
    raw = line.strip()
    if "{" not in raw:
        continue
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = scrape_truncated(raw)
    if isinstance(parsed, dict) and parsed:
        candidates.append(parsed)
scraped = scrape_truncated(text)
if scraped:
    candidates.append(scraped)
receipt = load_json(Path(sys.argv[2]))
if receipt:
    candidates.append(receipt)
payload = candidates[-1] if candidates else {}
look = glance_of(payload)
for candidate in candidates:
    cand = glance_of(candidate)
    if productive(cand):
        look = cand
        break
glance = {
    "ok": bool(look.get("ok")),
    "health": look.get("health") or "unknown",
    "progress": int(look.get("progress") or 0),
}
remaining = look.get("remaining")
if isinstance(remaining, dict) and remaining.get("issue_to_pr_started"):
    glance["issue_to_pr_started"] = remaining.get("issue_to_pr_started")
error = look.get("error")
if isinstance(error, str) and error:
    glance["error"] = error[:200]
print(json.dumps(glance, ensure_ascii=False, default=str))
PY
}

reopen_stdio_on_path() {
  # launchd keeps StandardOutPath open at the pre-truncate offset.
  # Compare inode (not path string: /var vs /private/var) and reopen so
  # the glance cannot punch a sparse GiB hole.
  local path="$1"
  [[ -n "${path}" && -f "${path}" ]] || return 0
  _python - "${path}" <<'PY'
import os, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    want = path.stat()
except OSError:
    raise SystemExit(0)

def same(fd: int) -> bool:
    try:
        got = os.fstat(fd)
    except OSError:
        return False
    return (got.st_dev, got.st_ino) == (want.st_dev, want.st_ino)

print("1" if same(1) else "0")
print("2" if same(2) else "0")
PY
}

bound_launchd_stdio() {
  # Small / missing StandardOutPath skips python inode reopen.
  # Fat logs still truncate in place, then reopen the truncated inode.
  local stdout_path fds fd size
  while IFS= read -r stdout_path; do
    [[ -n "${stdout_path}" && -f "${stdout_path}" ]] || continue
    size="$(wc -c < "${stdout_path}" 2>/dev/null || true)"
    size="${size// /}"
    case "${LAUNCHD_STDOUT_MAX}" in
      ''|*[!0-9]*) ;;
      *)
        if [[ -n "${size}" && "${size}" -le "${LAUNCHD_STDOUT_MAX}" ]]; then
          continue
        fi
        ;;
    esac
    bound_file "${stdout_path}" "${LAUNCHD_STDOUT_MAX}" || true
    fds="$(reopen_stdio_on_path "${stdout_path}" || true)"
    for fd in ${fds}; do
      case "${fd}" in
        1) exec >>"${stdout_path}" ;;
        2) exec 2>>"${stdout_path}" ;;
      esac
    done
  done < <(launchd_stdout_paths || true)
}

# Bound StandardOutPath before this tick appends a glance line.
bound_launchd_stdio

# Tick starts on current origin/main or fail-closed (do not mill on stale host code).
# Keep host-ff out of launchd stdout; the mill transcript owns that line.
# A live mill (i2pr / factory_pass) holds mill.lock. It blocks a second daemon,
# but must not freeze origin/main updates on disk.
MILL_LOCK_WAS_BUSY=0
if mill_lock_busy; then
  MILL_LOCK_WAS_BUSY=1
fi
: >"${LOG}"
# GitHub SHA already matches HEAD and origin/main. Skip caretaker host-ff.
# Fresh idle stamps skip the GitHub SHA probe. Busy lock still probes.
# Probe failure or SHA mismatch still hosts caretaker host-ff.
if host_ff_already_current "${ROOT}" "${MILL_LOCK_WAS_BUSY}" >>"${LOG}" 2>/dev/null; then
  :
elif ! uv run lokay-host-ff --config "${CFG}" --live --checkout "${ROOT}" >>"${LOG}" 2>&1; then
  bootstrap_incident "host_behind"
  bound_file "${LOG}" "${MILL_LOG_MAX}" || true
  emit_launchd_glance || true
  bound_launchd_stdio
  exit 78
fi
# factory_pass host_ff is the same checkout this tick. Do not fetch origin/main twice.
export LOKAY_HOST_FF_FETCHED=1
# Publish this tick immediately: lokay-daemon may run for minutes, and readers
# must not keep seeing the previous tick's terminal state in mill-latest.log.
cp "${LOG}" "${LATEST}" 2>/dev/null || true
bound_file "${LOG}" "${MILL_LOG_MAX}" || true
bound_file "${LATEST}" "${MILL_LOG_MAX}" || true
if [[ "${MILL_LOCK_WAS_BUSY}" -eq 1 ]]; then
  printf '%s\n' '{"ok":true,"health":"current","reason":"lock_busy"}' >>"${LOG}"
  cp "${LOG}" "${LATEST}" 2>/dev/null || true
  bound_file "${LOG}" "${MILL_LOG_MAX}" || true
  bound_file "${LATEST}" "${MILL_LOG_MAX}" || true
  prune_mill_logs || true
  emit_launchd_glance || true
  bound_launchd_stdio
  exit 0
fi
# HEAD moved on disk: this bash wrapper has not imported lokay. Continue
# into uv reinstall + lokay-daemon in the same tick. Waiting for
# StartInterval leaves the mill dark after every absorb. Live i2pr holds
# mill.lock (lock_busy above) and is not killed.
UV_REINSTALL_ARGS=()
CURRENT_DIGEST=""
PREVIOUS_DIGEST=""
if [[ -f "${DIGEST_FILE}" ]]; then
  PREVIOUS_DIGEST="$(cat "${DIGEST_FILE}" 2>/dev/null || true)"
fi
# Reinstall when lokay/Fala HEAD or lockfile moved, or the installed
# wheel still shadows a different checkout (digest can match after an
# overlap tick that never rebuilt). host-ff updated=true also forces a
# rebuild: fake/partial digest must not start the mill on a stale wheel.
# Fresh idle skip with a persisted digest skips checkout_digest and
# package_matches. Missing digest, host-ff update, or a hosted daemon
# still checks the wheel.
# already_current envelope already proved HEAD did not move. Skip python.
HOST_FF_MOVED=0
if grep -Eq '"already_current"[[:space:]]*:[[:space:]]*true' "${LOG}" 2>/dev/null; then
  :
elif host_ff_updated "${LOG}"; then
  HOST_FF_MOVED=1
fi
SKIP_REASON=""
if [[ "${HOST_FF_MOVED}" -eq 0 && -n "${PREVIOUS_DIGEST}" ]]; then
  SKIP_REASON="$(idle_skip_daemon)" || SKIP_REASON=""
fi
case "${SKIP_REASON}" in
  recent_empty_survey|recent_empty_survey_probe|recent_empty_leftover_probe) ;;
  *) SKIP_REASON="" ;;
esac
# Fresh idle skip (both stamps fresh) skips checkout_digest / package_matches.
# Probe skip still checks the wheel. Stale wheel, missing digest, or host-ff
# update still hosts and reinstalls.
if [[ "${SKIP_REASON}" != "recent_empty_survey" ]]; then
  CURRENT_DIGEST="$(checkout_digest || true)"
  if [[ -z "${CURRENT_DIGEST}" || "${CURRENT_DIGEST}" != "${PREVIOUS_DIGEST}" ]] || ! package_matches || [[ "${HOST_FF_MOVED}" -eq 1 ]]; then
    SKIP_REASON=""
    UV_REINSTALL_ARGS=(--reinstall-package lokay --reinstall-package fala)
  fi
fi
if [[ -n "${SKIP_REASON}" ]]; then
  printf '{"ok":true,"health":"idle","idle":true,"skipped":true,"reason":"%s","engine":"fala","path_id":"daemon_cycle","leftover_closeout":{"ok":true,"skipped":true,"reason":"recent_empty"}}\n' "${SKIP_REASON}" >>"${LOG}"
  MILL_RC=0
else
  set +e
  if [[ ${#UV_REINSTALL_ARGS[@]} -gt 0 ]]; then
    uv run "${UV_REINSTALL_ARGS[@]}" lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" >>"${LOG}" 2>&1
  else
    uv run lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" >>"${LOG}" 2>&1
  fi
  MILL_RC=$?
  set -e
fi
cp "${LOG}" "${LATEST}" 2>/dev/null || true
# Persist digest only after lokay-daemon emitted an envelope. host-ff writes
# health=current first; a failed uv reinstall must retry next tick.
# Overlap means this tick never loaded the new package into a factory pass.
# Do not close the digest gate on a contended lock — the next idle tick
# must still reinstall if the wheel drifted.
if [[ -n "${CURRENT_DIGEST}" ]] && ! grep -Eq '"health"[[:space:]]*:[[:space:]]*"overlap"' "${LOG}" 2>/dev/null && grep -Eq '"(engine|path_id|preflight|self_repair)"|"health"[[:space:]]*:[[:space:]]*"(progress|idle|waiting|repairing|stall|survey_error|self_repair|carrier_failed|work_remaining|host_updated|pass_ceiling)' "${LOG}" 2>/dev/null; then
  printf '%s\n' "${CURRENT_DIGEST}" > "${DIGEST_FILE}" || true
fi
bound_file "${LOG}" "${MILL_LOG_MAX}" || true
bound_file "${LATEST}" "${MILL_LOG_MAX}" || true
prune_mill_logs || true
bound_launchd_stdio
# Fresh idle skip already wrote health=idle. Do not spawn python glance.
if [[ -n "${SKIP_REASON}" ]]; then
  printf '{"ok":true,"health":"idle","progress":0}\n'
else
  emit_launchd_glance || true
fi
bound_launchd_stdio

# Self-repair writes this flag when activate+preflight released the gate.
if [[ -f "${LOKAY_HOME}/restart-required" ]]; then
  rm -f "${LOKAY_HOME}/restart-required" || true
  if ! mill_lock_busy; then
    reload_launchagent "${LOKAY_LAUNCHD_PLIST}" "${LOKAY_LAUNCHD_LABEL}" || true
  fi
fi
# Crash KeepAlive must load after this process exits. bootout here would
# kill the live mill. HOME=/Users is the operator host; pytest HOME is not.
# Stamp so a missed launchctl KeepAlive probe cannot RunAtLoad every tick.
# launchd kills the job process group on idle 0, so a `&` child dies with
# the tick. Double-fork + setsid detaches --install from that group.
if ! mill_lock_busy   && [[ "${HOME}" == /Users/* ]]   && [[ "${LOKAY_LAUNCHD_PLIST}" == "${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist" ]]   && [[ -f "${LOKAY_LAUNCHD_PLIST}" ]]   && [[ ! -f "${LOKAY_KEEPALIVE_STAMP}" ]]   && ! loaded_keepalive_crash_only "${LOKAY_LAUNCHD_LABEL}"; then
  _python - "$0" <<'PY' || true
import os
import sys
import time

script = sys.argv[1]
if os.fork() > 0:
    raise SystemExit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
devnull = os.open(os.devnull, os.O_RDWR)
os.dup2(devnull, 0)
os.dup2(devnull, 1)
os.dup2(devnull, 2)
if devnull > 2:
    os.close(devnull)
time.sleep(2)
os.execv("/bin/bash", ["/bin/bash", script, "--install"])
PY
fi
exit "${MILL_RC}"
