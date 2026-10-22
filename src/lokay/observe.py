from __future__ import annotations

from json import dumps
from lokay.store import write_heartbeat

import gzip
import json
import math
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Event, Thread
import sys

from lokay.config import HOME
from lokay.effects.gh import gh_json, gh_ok
from lokay.store import RUNS, main_status

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
                write_heartbeat(**CURRENT)
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
        write_heartbeat(**CURRENT)


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


def latest_needs_help() -> dict:
    from lokay.replay import unpack

    latest = None
    unreadable = 0
    directory = RUNS.parent / "ticks"
    for path in (*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz")):
        try:
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        if row.get("kind") != "transition":
                            continue
                        event = unpack(row.get("event"), directory, source=directory)
                        if event.get("action") != "needs_help":
                            continue
                        ts = float(event["ts"])
                        if not math.isfinite(ts):
                            raise ValueError("invalid event timestamp")
                        before = unpack(row.get("before", {}), directory, source=directory)
                        if latest is None or ts > latest["ts"]:
                            latest = {"ts": ts, "time": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                                      "repo": row.get("repo"), "issue": row.get("issue"),
                                      "node": before.get("node", row.get("node")), "event": event}
                    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError, EOFError):
                        unreadable += 1
        except (OSError, EOFError, UnicodeError):
            unreadable += 1
    return {"latest_needs_help": latest, "unreadable_records_or_files": unreadable}


def monitor() -> dict:
    path = HOME / "heartbeat.json"
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
    repo = os.environ.get("LOKAY_ALARM_REPO", "mikolaj92/lokay")
    rows = gh_json(["issue", "list", "--repo", repo, "--state", "open",
                    "--search", "lokay-stalled in:title", "--limit", "1000000", "--json", "number,title"],
                   error="alarm lookup failed", strip=False, default="[]")
    alarms = [row for row in rows if row["title"] == "lokay-stalled"]
    evidence = "\n\n```json\n" + dumps(beat, indent=2) + "\n```"
    if not reasons:
        for alarm in alarms:
            gh_ok(["issue", "close", str(alarm["number"]), "--repo", repo,
                   "--comment", "Monitor recovered: no stall predicates remain." + evidence],
                  error="alarm closure failed", strip=False)
        return {"result": "ok", "closed": [alarm["number"] for alarm in alarms]}
    if not alarms:
        body = "\n".join(reasons) + evidence + "\n\n```json\n" + dumps(latest_needs_help(), indent=2) + "\n```"
        gh_ok(["issue", "create", "--repo", repo, "--title", "lokay-stalled", "--body", body],
              error="alarm creation failed", strip=False)
    return {"result": "stalled", "reasons": reasons}
