from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from json import dumps as dumps
from tempfile import NamedTemporaryFile
from importlib.metadata import PackageNotFoundError, version
from threading import RLock
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay import graph
from lokay.config import HOME
from lokay.redact import redact_text
from lokay.types import PLAN_RESET, CheckResult, Event, Run, event_record, parse_event, pr_number

RUNS = HOME / "runs"
LOCKS = HOME / "locks"
TICK = str(uuid.uuid4())
SEQ = 0
CONTEXT: dict = {}
EVENT_LOCK = RLock()


def prune_blobs(directory: Path) -> None:
    references = set()
    for path in (*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz")):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                references.update(re.findall(r'"blob"\s*:\s*"sha256:([a-f0-9]{64})"', line))
    for blob in (directory / "blobs").glob("*"):
        if blob.name.removesuffix(".gz") not in references:
            blob.unlink()


def redact(value, env=None) -> Any:
    def clean(item):
        if isinstance(item, dict):
            return {clean(str(key)): "[REDACTED]" if re.search(
                r"^(?:env|environ|environment|.*headers?|authorization|proxy-authorization|(?:.*[_-])?(?:token|secret|password|api[_-]?key))$",
                str(key), re.IGNORECASE) else clean(value) for key, value in item.items()}
        if isinstance(item, list):
            result = []
            header = False
            for value in item:
                if header:
                    result.append("[REDACTED]")
                    header = False
                    continue
                header = isinstance(value, str) and (value in ("-H", "--header", "--headers") or bool(re.fullmatch(
                    r"--(?:.*-)?(?:token|secret|password|api-key)", value, re.IGNORECASE)))
                result.append("[REDACTED]" if isinstance(value, str) and re.match(
                    r"^(?:-H.+|--headers?=|--(?:.*-)?(?:token|secret|password|api-key)=)", value, re.IGNORECASE) else clean(value))
            return result
        if isinstance(item, bytes):
            item = item.decode(errors="replace")
        if not isinstance(item, str):
            return item
        return redact_text(item, env)

    return clean(json.loads(json.dumps(value, ensure_ascii=False,
                                       default=lambda item: item.decode(errors="replace") if isinstance(item, bytes) else json_default(item))))


def write_blob(directory: Path, raw: bytes) -> dict:
    sha = hashlib.sha256(raw).hexdigest()
    blobs = directory / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    temporary = blobs / (sha + ".gz.tmp")
    with gzip.open(temporary, "wb") as stream:
        stream.write(raw)
    temporary.replace(blobs / (sha + ".gz"))
    return {"blob": "sha256:" + sha}


def write_segment(directory: Path, source: Path, manifest: dict, rows: list[dict]) -> None:
    from lokay.replay import unpack

    def materialize(value) -> Any:
        if isinstance(value, dict):
            if set(value) == {"blob"}:
                return materialize(unpack(value, source, source=source))
            return {key: materialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [materialize(item) for item in value]
        return value

    files = set(manifest.get("files", {}).values())
    if manifest.get("entry") == "check":
        files.add(manifest["diff"])
    for name in files:
        origin = (source / name).resolve()
        target = (directory / name).resolve()
        if not origin.is_relative_to(source.resolve()) or not target.is_relative_to(directory.resolve()):
            raise ValueError("fixture file escapes fixture directory")
    directory.mkdir(parents=True, exist_ok=False)
    for name in files:
        write_artifact(directory / name, (source / name).read_text())
    packed = []
    for seq, row in enumerate(rows, 1):
        row = {**materialize(row), "seq": seq}
        for key in ("effect", "before", "event", "after", "output"):
            if key not in row:
                continue
            raw = json.dumps(row[key], sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=json_default).encode()
            if key == "effect" or len(raw) > 768:
                row[key] = write_blob(directory, raw)
        packed.append(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")
    write_artifact(directory / "segment.jsonl", "".join(packed))
    write_json(directory / "segment.json", manifest)


def log_event(kind: str, *, _env=None, **fields) -> None:
    global TICK, SEQ, CONTEXT
    try:
        fields = redact(fields, _env)
        with shared_file_lock(RUNS.parent / "events.lock"):
            directory = RUNS.parent / "ticks"
            now = datetime.now(timezone.utc)
            if kind == "start":
                TICK, SEQ, CONTEXT = str(uuid.uuid4()), 0, {}
                directory.mkdir(parents=True, exist_ok=True)
                for path in (*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz")):
                    age = (now.date() - datetime.strptime(path.name[:10], "%Y-%m-%d").date()).days
                    if age > 180:
                        path.unlink()
                    elif age > 1 and path.suffix == ".jsonl":
                        temporary = path.with_suffix(".jsonl.gz.tmp")
                        with path.open("rb") as source, gzip.open(temporary, "wb") as target:
                            shutil.copyfileobj(source, target)
                        temporary.replace(path.with_suffix(".jsonl.gz"))
                        path.unlink()
                prune_blobs(directory)
                for blob in (directory / "blobs").glob("*"):
                    if re.fullmatch(r"[a-f0-9]{64}", blob.name) and now.timestamp() - blob.stat().st_mtime > 86400:
                        temporary = blob.with_suffix(".gz.tmp")
                        with blob.open("rb") as source, gzip.open(temporary, "wb") as target:
                            shutil.copyfileobj(source, target)
                        temporary.replace(blob.with_suffix(".gz"))
                        blob.unlink()
                maximum = max(0, float(os.environ.get("LOKAY2_TICKS_MAX_MB", "300"))) * 1024 * 1024
                size = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
                if size <= maximum:
                    return
                kind = "ticks_over_cap"
                fields = {"size": size}
            CONTEXT.update({key: fields[key] for key in ("repo", "issue", "node") if key in fields})
            if kind == "context":
                return
            SEQ += 1
            row = {"v": 1, "ts": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                   "tick": TICK, "seq": SEQ, "repo": None, "issue": None, "node": None,
                   **CONTEXT, "kind": kind, **fields}
            if kind == "call":
                effect = row.pop("effect", {"input": row["input"], "output": row.get("output")})
                row["effect"] = write_blob(directory, json.dumps(effect, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=json_default).encode())
                value = row.pop("input")
                raw = value.encode() if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=json_default).encode()
                row["input"] = "sha256:" + hashlib.sha256(raw).hexdigest()
                row["ms"] = round((time.monotonic() - row.pop("started")) * 1000)
            for key in ("output", "before", "event", "after"):
                if key not in row:
                    continue
                raw = json.dumps(row[key], sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=json_default).encode()
                sha = hashlib.sha256(raw).hexdigest()
                if key == "output":
                    row["output_sha"] = "sha256:" + sha
                if kind == "call":
                    if key == "output":
                        value = row[key]
                        if isinstance(value, dict):
                            value = {k: v[:500] if isinstance(v, str) else v
                                     for k, v in value.items() if k in ("result", "reason", "returncode", "next")}
                            if len(json.dumps(value, ensure_ascii=False, default=json_default).encode()) <= 2048:
                                row[key] = value
                                continue
                        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=json_default)
                        text = text.encode()[:2048].decode("utf-8", errors="ignore")
                        while len(json.dumps(text, ensure_ascii=False).encode()) > 2048:
                            text = text[:-1]
                        row[key] = text
                    else:
                        row.pop(key)
                    continue
                if len(raw) > (2048 if key == "output" else 768):
                    row[key] = write_blob(directory, raw)
            line = json.dumps(row, separators=(",", ":"), ensure_ascii=False, default=json_default) + "\n"
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / f"{now:%Y-%m-%d}.jsonl").open("a") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        return


def ledger_append(row: dict) -> None:
    path = RUNS.parent / "ledger.jsonl"
    with shared_file_lock(path.with_suffix(".lock")):
        append_text(path, dumps({**row, "ts": datetime.now(timezone.utc).isoformat(), "tick": TICK}) + "\n")


def run_dir(repo: str, issue: int) -> Path:
    return RUNS / repo.replace("/", "__") / str(issue)


def main_status(home: Path | None = None) -> dict:
    directory = home / "runs" if home is not None else RUNS
    return {path.parent.name.replace("__", "/"): json.loads(path.read_text())
            for path in directory.glob("*/main.json")}


def save_main_status(repo: str, status: dict) -> None:
    path = RUNS / repo.replace("/", "__") / "main.json"
    write_json(path, status)


def repo_last_attempt(repo: str) -> float:
    directory = RUNS / repo.replace("/", "__")
    attempt = directory / "attempt.json"
    latest = json.loads(attempt.read_text())["last_attempt"] if attempt.exists() else 0
    return max(latest, max((json.loads(path.read_text()).get("last_attempt", 0)
                           for path in directory.glob("*/state.json")), default=0))


def repo_attempt(repo: str, timestamp: float) -> None:
    path = RUNS / repo.replace("/", "__") / "attempt.json"
    write_json(path, {"last_attempt": timestamp})


def escalation_fields(state: dict) -> dict:
    levels = ("easy", "medium", "hard", "too_big")
    difficulty = state.get("difficulty")
    if difficulty not in levels:
        difficulty = "easy"
    return {
        "difficulty": levels[min(levels.index(difficulty) + 1, 2 if state.get("pr") is not None else 3)],
        "node": "plan", "result": "pending", "retry_at": 0, "awaiting": None,
        "no_progress": 0, "fix_history": [], "fix_counts": [],
        **deepcopy(PLAN_RESET), "plan_prompt": None, "plan_notes": [],
        "wait_escape": None, "verdict": None, "failures": 0, "last_error": None,
        "reason": None, "ladder_since": time.time(),
    }


def last_activity(state: dict) -> float:
    try:
        updated_at = datetime.fromisoformat(state.get("updated_at")).timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        updated_at = 0
    return max(state.get("last_attempt", 0), updated_at)


def ladder_start(state: dict, now: float) -> float:
    return max(state.get("diff_changed_at") or state.get("issue_since")
               or state.get("ladder_since") or now, state.get("ladder_since") or 0)


def pick_ladder_fields(state: dict, now: float) -> dict:
    activity = last_activity(state)
    if any(state.get(key) for key in ("diff_changed_at", "issue_since", "ladder_since")) and activity > 0:
        return {"ladder_since": ladder_start(state, now) + (now - activity)}
    return {}


def empty_patch(repo: str, issue: int, sha: str | None = None) -> dict:
    from lokay.config import repo as repo_config
    from lokay.effects.git import base_branch, git

    if not sha:
        root = Path(repo_config(repo)["clone_path"]).expanduser()
        sha = git(root, "rev-parse", f"origin/{base_branch(root)}")
    state_update(repo, issue, _event={"action": "build_complete", "outcome": {
        "no_changes": True, "main_sha": sha}})
    return {"result": state_read(repo, issue)["result"], "reason": "empty patch", "empty_main_sha": sha}


def derive_waiting_on(state: dict, now: float | None = None) -> str | None:
    if state.get("result") == "closed":
        return None
    if state.get("result") == "empty_patch":
        return "main"
    now = time.time() if now is None else now
    if state.get("awaiting") == "children":
        return "children"
    if state.get("result") == "parked":
        return "ready"
    if state.get("result") == "wait":
        return "retry_at" if state.get("retry_at", 0) > now else "ready"
    if state.get("retry_at", 0) > now:
        return "retry_at"
    if (state.get("result") == "pending" and state.get("node") in ("check", "build")
            and last_activity(state) > now - 300):
        return "ci"
    return "ready"


def state_read(repo: str, issue: int) -> dict:
    path = run_dir(repo, issue) / "state.json"
    if not path.exists():
        return {}
    state = json.loads(path.read_text())
    normalize_state(state)
    state["waiting_on"] = derive_waiting_on(state)
    return state


def state_update(repo: str, issue: int, **fields) -> Path:
    event = {"ts": time.time(), **fields.pop("_event", {}), "fields": fields}
    if "node" in fields:
        raise ValueError("node must be set through an enter_node event")
    run = load(repo, issue)
    event = parse_event(event)
    run = graph.step(run, event)
    save(repo, issue, run, event)
    return run_dir(repo, issue) / "state.json"


def round_fields(state: dict, *, diff_fingerprint: str | None = None,
                 checks=None, accepted_plan: bool = False, completed: bool = True) -> dict:
    previous_diff = state.get("progress_diff_fingerprint")
    previous_checks = state.get("progress_checks") or {}
    current_checks = {}
    for check in checks or ():
        if isinstance(check, CheckResult):
            name, status = check.name, check.status
        else:
            name = check.get("name")
            status = check.get("status")
            if status is None:
                status = "pass" if check.get("pass") is True else "fail" if check.get("pass") is False else "unknown"
        if name:
            current_checks[name] = status
    progressed = (diff_fingerprint is not None and previous_diff is not None
                  and diff_fingerprint != previous_diff) or any(
        status == "pass" and previous_checks.get(name) == "fail"
        for name, status in current_checks.items())
    progressed = progressed or (completed and checks is not None and state.get("progress_pending", False))
    fields = {"no_progress": 0 if accepted_plan or progressed else state.get("no_progress", 0) + int(completed)}
    if diff_fingerprint is not None and diff_fingerprint != previous_diff:
        fields["diff_changed_at"] = time.time()
    if (completed and checks is not None) or accepted_plan:
        fields["progress_pending"] = False
    elif progressed:
        fields["progress_pending"] = True
    if diff_fingerprint is not None:
        fields["progress_diff_fingerprint"] = diff_fingerprint
    if current_checks:
        fields["progress_checks"] = {**previous_checks, **current_checks}
    return fields


def load(repo: str, issue: int) -> Run:
    return Run.from_state({key: value for key, value in state_read(repo, issue).items()
                           if key != "updated_at"})


def save(repo: str, issue: int, run: Run, event: Event) -> None:
    before = load(repo, issue).state
    current = dict(run.state)
    raw = event_record(event)
    from lokay.observe import current as observe_current

    failures = current.get("failures", 0)
    reason = (current.get("reason") or current.get("last_error")) if failures else None
    result = "failed" if failures and current.get("reason") else current.get("result", "running")
    observe_current(repo=repo, issue=issue, node=current.get("node"),
                    node_since=current.get("node_since"), result=result,
                    issue_since=current.get("issue_since"), idle_reason=None,
                    failures=failures, last_error=reason)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_run(repo, issue, current)
    after = {key: value for key, value in current.items() if key != "updated_at"}
    log_event("context", repo=repo, issue=issue, node=current.get("node"))
    if before != after:
        log_event("transition", repo=repo, issue=issue, node=current.get("node"),
                  event=raw, before=before, after=after)


def rounds_append(repo: str, issue: int, line: str) -> Path:
    path = run_dir(repo, issue) / "rounds.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(f"- {datetime.now(timezone.utc).isoformat()} {line}\n")
    return path


def write_artifact(path: Path, text: str | bytes) -> None:
    ensure_directory(path.parent)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)


def freeze_dataset(path: Path, payload: dict) -> None:
    ensure_directory(path.parent)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                            prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def remove_directory(path: Path) -> None:
    shutil.rmtree(path)


def append_text(path: Path, text: str) -> None:
    ensure_directory(path.parent)
    with path.open("a") as stream:
        stream.write(text)


def write_text_atomic(path: Path, text: str, *, temporary: Path | None = None) -> None:
    ensure_directory(path.parent)
    with NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name + ".",
                            suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(text)
            file.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def json_default(value: object) -> dict | str:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def write_json(path: Path, value: object, *, indent: int | None = None,
               ensure_ascii: bool = True) -> None:
    write_text_atomic(path, json.dumps(value, indent=indent, ensure_ascii=ensure_ascii, default=json_default) + "\n")


def normalize_state(state: dict) -> None:
    if state.get("node") == "plan" and state.get("difficulty") == "hard" and (state.get("plan_branches") or state.get("plan_synthesis")):
        state.update(deepcopy(PLAN_RESET), node="plan", result="pending", retry_at=0,
                     awaiting=None, failures=0, reason=None, last_error=None, plan_rounds=0,
                     plan_prompt=None, plan_notes=[], fix_history=[], fix_counts=[])
    if state.get("plan_phase") is not None and state["plan_phase"] not in ("write", "check"):
        state["plan_phase"] = "write"
    if "pr" in state:
        state["pr"] = pr_number(state["pr"])
    if state.get("pr") is not None and state.get("difficulty") == "too_big":
        state["difficulty"] = "hard"
    if "awaiting" in state and state["awaiting"] not in (None, "children"):
        state["awaiting"] = None
        if state.get("result") == "wait" and not state.get("wait_escape"):
            state.update(retry_at=time.time(), wait_escape="retry")


def save_run(repo: str, issue: int, state: dict) -> None:
    normalize_state(state)
    state["waiting_on"] = derive_waiting_on(state)
    write_json(run_dir(repo, issue) / "state.json",
               {key: value for key, value in state.items() if key != "waiting_on"}, indent=2)


def worker_index() -> str | None:
    worker = os.environ.get("LOKAY2_WORKER")
    if worker is not None and worker not in ("0", "1", "2"):
        raise ValueError("LOKAY2_WORKER must be 0, 1 or 2")
    return worker


def process_groups_path() -> Path:
    worker = worker_index()
    directory = Path(os.environ["LOKAY_STATE_DIR"]) if os.environ.get("LOKAY_STATE_DIR") else HOME
    return directory / ("procs.json" if worker is None else f"procs-{worker}.json")


def save_process_groups(pgids: list[int]) -> None:
    write_text_atomic(process_groups_path(), json.dumps(pgids))


@contextmanager
def shared_file_lock(path: Path):
    import fcntl

    with EVENT_LOCK:
        ensure_directory(path.parent)
        with path.open("a+") as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def write_heartbeat(result: str | None = None, **fields) -> dict:
    from lokay.effects.git import checkout_version

    path = HOME / "heartbeat.json"
    with shared_file_lock(path.with_suffix(".lock")):
        previous = json.loads(path.read_text()) if path.exists() else {}
        worker = worker_index()
        keys = ("time", "version", "result", "repo", "issue", "node", "node_since",
                "failures", "last_error", "idle_reason", "issue_since", "queue_since",
                "last_merge", "worker")
        snapshots = previous.get("workers", {})
        workers = {index: {key: snapshot[key] for key in keys if key in snapshot}
                   for index in ("0", "1", "2")
                   if isinstance(snapshots, dict) and isinstance(snapshot := snapshots.get(index), dict)}
        previous = workers.get(worker, {}) if worker is not None else previous
        previous = {key: previous[key] for key in keys if key in previous}
        if worker is not None:
            previous["worker"] = worker
        previous.setdefault("failures", 0)
        previous.setdefault("last_error", None)
        previous.setdefault("idle_reason", None)
        previous.setdefault("issue_since", None)
        previous.update({key: fields[key] for key in keys if key in fields})
        if fields.get("failures") == 0:
            previous["last_error"] = None
        if result is not None:
            previous["result"] = result
        if previous.get("idle_reason") == "no_work":
            previous["queue_since"] = None
        elif result == "merged":
            previous["last_merge"] = time.time()
            previous["queue_since"] = time.time()
        elif fields.get("repo") and not previous.get("queue_since"):
            previous["queue_since"] = fields.get("issue_since") or time.time()
        try:
            installed = version("lokay")
        except PackageNotFoundError:
            installed = "unknown"
        previous.update(time=datetime.now(timezone.utc).isoformat(),
                        version=checkout_version() or os.environ.get("LOKAY_VERSION") or installed)
        if worker is not None:
            workers[worker] = dict(previous)
        if workers:
            previous["workers"] = workers
        previous["main_status"] = {
            repo: {key: status[key] for key in ("status", "since", "culprit", "issue") if key in status}
            for repo, status in main_status().items()
        }
        write_json(path, previous)
        return previous


def lock_path(owner: str, repo: str) -> Path:
    safe = repo.replace("/", "__")
    return LOCKS / f"{owner}__{safe}.lock"


def acquire_lock(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
    except BlockingIOError:
        os.close(fd)
        return {"result": "busy", "path": str(path)}
    except BaseException:
        os.close(fd)
        raise
    return {"result": "held", "fd": fd, "path": str(path)}


def release_lock(held: dict) -> None:
    fd = held.pop("fd", None)
    if not isinstance(fd, int):
        return
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
