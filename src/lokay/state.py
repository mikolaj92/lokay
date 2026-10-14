from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from threading import RLock
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path.home() / ".lokay" / "runs"
TICK = str(uuid.uuid4())
SEQ = 0
CONTEXT: dict = {}
EVENT_LOCK = RLock()


def log_event(kind: str, **fields) -> None:
    global TICK, SEQ, CONTEXT
    try:
        with EVENT_LOCK:
            directory = RUNS.parent / "ticks"
            now = datetime.now(timezone.utc)
            if kind == "start":
                TICK, SEQ, CONTEXT = str(uuid.uuid4()), 0, {}
                directory.mkdir(parents=True, exist_ok=True)
                for path in directory.glob("*.jsonl*"):
                    age = (now.date() - datetime.strptime(path.name[:10], "%Y-%m-%d").date()).days
                    if age > 180:
                        path.unlink()
                    elif age > 30 and path.suffix == ".jsonl":
                        temporary = path.with_suffix(".jsonl.gz.tmp")
                        with path.open("rb") as source, gzip.open(temporary, "wb") as target:
                            shutil.copyfileobj(source, target)
                        temporary.replace(path.with_suffix(".jsonl.gz"))
                        path.unlink()
                references = set()
                for path in directory.glob("*.jsonl*"):
                    opener = gzip.open if path.suffix == ".gz" else open
                    with opener(path, "rt") as stream:
                        for line in stream:
                            references.update(re.findall(r'sha256:([a-f0-9]{64})', line))
                for blob in (directory / "blobs").glob("*"):
                    if blob.name not in references:
                        blob.unlink()
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
            for key in ("output", "before", "after"):
                if key not in row:
                    continue
                raw = json.dumps(row[key], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                sha = hashlib.sha256(raw).hexdigest()
                if key == "output":
                    row["output_sha"] = "sha256:" + sha
                if len(raw) > (2048 if key == "output" else 768):
                    blobs = directory / "blobs"
                    blobs.mkdir(parents=True, exist_ok=True)
                    with (blobs / sha).open("wb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(status) + "\n")
    temporary.replace(path)


def repo_last_attempt(repo: str) -> float:
    directory = RUNS / repo.replace("/", "__")
    attempt = directory / "attempt.json"
    latest = json.loads(attempt.read_text())["last_attempt"] if attempt.exists() else 0
    return max(latest, max((json.loads(path.read_text()).get("last_attempt", 0)
                           for path in directory.glob("*/state.json")), default=0))


def repo_attempt(repo: str, timestamp: float) -> None:
    path = RUNS / repo.replace("/", "__") / "attempt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"last_attempt": timestamp}) + "\n")
    temporary.replace(path)


def state_read(repo: str, issue: int) -> dict:
    path = run_dir(repo, issue) / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def state_update(repo: str, issue: int, **fields) -> Path:
    path = run_dir(repo, issue) / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text()) if path.exists() else {}
    before = {key: value for key, value in current.items() if key != "updated_at"}
    if "node" in fields and (fields["node"] != current.get("node") or "node_since" not in current):
        current["node_since"] = time.time()
    if fields.get("last_attempt") and not current.get("issue_since"):
        current["issue_since"] = time.time()
    if fields.get("result") == "merged":
        current["issue_since"] = None
    current.update(fields)
    from lokay.observe import current as observe_current

    failures = current.get("failures", 0)
    reason = (current.get("reason") or current.get("last_error")) if failures else None
    result = "failed" if failures and current.get("reason") else current.get("result", "running")
    if fields.get("failures") == 0 and "result" not in fields and current.get("result") == "failed":
        current["result"] = result = "running"
    observe_current(repo=repo, issue=issue, node=current.get("node"),
                    node_since=current.get("node_since"), result=result,
                    issue_since=current.get("issue_since"), idle_reason=None,
                    failures=failures, last_error=reason)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(current, indent=2) + "\n")
    temporary.replace(path)
    after = {key: value for key, value in current.items() if key != "updated_at"}
    log_event("context", repo=repo, issue=issue, node=current.get("node"))
    if before != after:
        event = (fields.get("result") or
                 (f"{before.get('node') or 'start'}->{after.get('node')}"
                  if before.get("node") != after.get("node") else after.get("result") or after.get("node") or "updated"))
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
