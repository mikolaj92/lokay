from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import Event, Thread
from tempfile import NamedTemporaryFile
import sys

from lokay.gh import _gh
from lokay.state import RUNS, main_status

CURRENT: dict = {}


def current(**fields) -> None:
    global CURRENT
    CURRENT = {**CURRENT, **fields}


@contextmanager
def ticking():
    stopped = Event()
    current(result="running", repo=None, issue=None, node=None, node_since=None,
            issue_since=None, idle_reason=None, failures=0, last_error=None)

    def pulse():
        while not stopped.is_set():
            try:
                heartbeat(**CURRENT)
            except Exception as exc:
                print(f"heartbeat failed: {exc}", file=sys.stderr)
            stopped.wait(float(os.environ.get("LOKAY_TICK_SECONDS", "60")))

    thread = Thread(target=pulse, daemon=True)
    thread.start()
    try:
        yield
    except BaseException:
        current(result="failed")
        raise
    finally:
        stopped.set()
        thread.join()
        heartbeat(**CURRENT)


def heartbeat(result: str | None = None, **fields) -> dict:
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
    # Concurrent pulses must not share the file used for atomic replacement.
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


def status() -> None:
    rows = [["REPO", "ISSUE", "NODE", "RESULT", "UPDATED"]]
    for path in sorted(RUNS.glob("*/*/state.json")):
        state = json.loads(path.read_text())
        rows.append([path.parent.parent.name.replace("__", "/"), path.parent.name,
                     str(state.get("node", "-")), str(state.get("result", "-")),
                     state.get("updated_at", "-")])
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))


def monitor() -> dict:
    path = Path.home() / ".lokay" / "heartbeat.json"
    reasons = []
    try:
        beat = json.loads(path.read_text())
        age = time.time() - datetime.fromisoformat(beat["time"]).timestamp()
        if age > float(os.environ.get("LOKAY_HEARTBEAT_MINUTES", "5")) * 60:
            reasons.append(f"Heartbeat age: {age / 60:.1f} minutes")
        if beat.get("idle_reason") in ("idle_backoff", "host_down"):
            reasons.append(f"Idle: {beat['idle_reason']}")
        if beat.get("failures", 0) >= 3:
            reasons.append(f"Failures: {beat['failures']}; last_error: {beat.get('last_error')}")
        issue_age = time.time() - (beat.get("issue_since") or time.time())
        if beat.get("issue_since") and issue_age > float(os.environ.get("LOKAY_ISSUE_MINUTES", "60")) * 60:
            reasons.append(f"Issue {beat.get('issue')} age: {issue_age / 60:.1f} minutes")
        queue_age = time.time() - (beat.get("queue_since") or time.time())
        if beat.get("queue_since") and queue_age > float(os.environ.get("LOKAY_MERGE_HOURS", "1")) * 3600:
            reasons.append(f"No merge with queued work: {queue_age / 3600:.1f} hours")
        node_age = time.time() - (beat.get("node_since") or time.time())
        if beat.get("node") and node_age > float(os.environ.get("LOKAY_NODE_MINUTES", "60")) * 60:
            reasons.append(f"Node {beat['node']} age: {node_age / 60:.1f} minutes")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        beat = {}
        reasons.append(f"Heartbeat unavailable: {exc}")
    if not reasons:
        return {"result": "ok"}
    repo = os.environ.get("LOKAY_ALARM_REPO", "mikolaj92/lokay")
    code, out, err = _gh(["issue", "list", "--repo", repo, "--state", "open",
                          "--search", "lokay-stalled in:title", "--json", "number,title"])
    if code != 0:
        raise RuntimeError(err or "alarm lookup failed")
    if not any(row["title"] == "lokay-stalled" for row in json.loads(out or "[]")):
        body = "\n".join(reasons) + "\n\n```json\n" + json.dumps(beat, indent=2) + "\n```"
        code, _, err = _gh(["issue", "create", "--repo", repo, "--title", "lokay-stalled", "--body", body])
        if code != 0:
            raise RuntimeError(err or "alarm creation failed")
    return {"result": "stalled", "reasons": reasons}
