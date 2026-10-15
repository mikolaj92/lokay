from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from json import dumps as dumps
from tempfile import NamedTemporaryFile
from importlib.metadata import PackageNotFoundError, version
from threading import RLock
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path.home() / ".lokay" / "runs"
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


def log_event(kind: str, **fields) -> None:
    global TICK, SEQ, CONTEXT
    try:
        with EVENT_LOCK:
            directory = RUNS.parent / "ticks"
            now = datetime.now(timezone.utc)
            if kind == "start":
                TICK, SEQ, CONTEXT = str(uuid.uuid4()), 0, {}
                directory.mkdir(parents=True, exist_ok=True)
                for path in (*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz")):
                    age = (now.date() - datetime.strptime(path.name[:10], "%Y-%m-%d").date()).days
                    if age > 180:
                        path.unlink()
                    elif age > 30 and path.suffix == ".jsonl":
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
                for path in sorted((*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz"))):
                    if size <= maximum:
                        break
                    if path.name[:10] >= f"{now:%Y-%m-%d}":
                        continue
                    path.unlink()
                    prune_blobs(directory)
                    size = sum(item.stat().st_size for item in directory.rglob("*") if item.is_file())
                return
            CONTEXT.update({key: fields[key] for key in ("repo", "issue", "node") if key in fields})
            if kind == "context":
                return
            SEQ += 1
            row = {"v": 1, "ts": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                   "tick": TICK, "seq": SEQ, "repo": None, "issue": None, "node": None,
                   **CONTEXT, "kind": kind, **fields}
            if kind == "call":
                value = row.pop("input")
                raw = value.encode() if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                row["input"] = "sha256:" + hashlib.sha256(raw).hexdigest()
                row["ms"] = round((time.monotonic() - row.pop("started")) * 1000)
            for key in ("output", "before", "event", "after"):
                if key not in row:
                    continue
                raw = json.dumps(row[key], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                sha = hashlib.sha256(raw).hexdigest()
                if key == "output":
                    row["output_sha"] = "sha256:" + sha
                if kind == "call":
                    if key == "output":
                        value = row[key]
                        if isinstance(value, dict):
                            value = {k: v[:500] if isinstance(v, str) else v
                                     for k, v in value.items() if k in ("result", "reason", "returncode", "next")}
                            if len(json.dumps(value, ensure_ascii=False).encode()) <= 2048:
                                row[key] = value
                                continue
                        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                        text = text.encode()[:2048].decode("utf-8", errors="ignore")
                        while len(json.dumps(text, ensure_ascii=False).encode()) > 2048:
                            text = text[:-1]
                        row[key] = text
                    else:
                        row.pop(key)
                    continue
                if len(raw) > (2048 if key == "output" else 768):
                    blobs = directory / "blobs"
                    blobs.mkdir(parents=True, exist_ok=True)
                    temporary = blobs / (sha + ".gz.tmp")
                    with gzip.open(temporary, "wb") as stream:
                        stream.write(raw)
                    temporary.replace(blobs / (sha + ".gz"))
                    row[key] = {"blob": "sha256:" + sha}
            line = json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / f"{now:%Y-%m-%d}.jsonl").open("a") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        return


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


def state_read(repo: str, issue: int) -> dict:
    path = run_dir(repo, issue) / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def state_update(repo: str, issue: int, **fields) -> Path:
    path = run_dir(repo, issue) / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text()) if path.exists() else {}
    before = {key: value for key, value in current.items() if key != "updated_at"}
    from lokay.start import step

    event = {"ts": time.time(), **fields.pop("_event", {}), "fields": fields}
    current = step(before, event)
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
                  event=event, before=before, after=after)
    return path


def rounds_append(repo: str, issue: int, line: str) -> Path:
    path = run_dir(repo, issue) / "rounds.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(f"- {datetime.now(timezone.utc).isoformat()} {line}\n")
    return path


def run_path(owner: str, repo: str, issue: int) -> Path:
    return run_dir(repo if "/" in repo else f"{owner}/{repo}", issue) / "state.json"


def write_run(owner: str, repo: str, issue: int, fields: dict) -> Path:
    return state_update(repo if "/" in repo else f"{owner}/{repo}", issue, **fields)


def read_run(owner: str, repo: str, issue: int) -> dict:
    return state_read(repo if "/" in repo else f"{owner}/{repo}", issue)


def write_artifact(path: Path, text: str) -> None:
    ensure_directory(path.parent)
    path.write_text(text)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def append_text(path: Path, text: str) -> None:
    ensure_directory(path.parent)
    with path.open("a") as stream:
        stream.write(text)


def write_text_atomic(path: Path, text: str, *, temporary: Path | None = None) -> None:
    ensure_directory(path.parent)
    temporary = temporary if temporary is not None else path.with_suffix(".json.tmp")
    temporary.write_text(text)
    temporary.replace(path)


def write_json(path: Path, value: object, *, indent: int | None = None,
               ensure_ascii: bool = True) -> None:
    write_text_atomic(path, json.dumps(value, indent=indent, ensure_ascii=ensure_ascii) + "\n")


def load_run(repo: str, issue: int) -> dict:
    return state_read(repo, issue)


def save_run(repo: str, issue: int, state: dict) -> None:
    write_json(run_dir(repo, issue) / "state.json", state, indent=2)


def append_tick(kind: str, **fields) -> None:
    log_event(kind, **fields)


def save_process_groups(pgids: list[int]) -> None:
    path = Path.home() / ".lokay" / "procs.json"
    write_text_atomic(path, json.dumps(pgids), temporary=path.with_suffix(f".{os.getpid()}.tmp"))


def write_heartbeat(result: str | None = None, **fields) -> dict:
    path = Path.home() / ".lokay" / "heartbeat.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    previous.setdefault("failures", 0)
    previous.setdefault("last_error", None)
    previous.setdefault("idle_reason", None)
    previous.setdefault("issue_since", None)
    previous.update(fields)
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
    previous["main_status"] = main_status()
    previous.update(time=datetime.now(timezone.utc).isoformat(),
                    version=os.environ.get("LOKAY_VERSION", installed))
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=path.parent, prefix="heartbeat.",
                            suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(json.dumps(previous) + "\n")
            file.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return previous


def acquire_lock(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return {"result": "busy", "path": str(path)}
    os.write(fd, str(os.getpid()).encode())
    return {"result": "held", "fd": fd, "path": str(path)}


def release_lock(held: dict) -> None:
    fd = held.pop("fd", None)
    if not isinstance(fd, int):
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
