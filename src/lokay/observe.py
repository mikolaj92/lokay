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
from lokay.effects.gh import STALL_TITLE, STALL_MARKER, stall_alarm, gh_json, gh_ok
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
    for entry in outside_factory():
        print("outside factory " + dumps(entry))


def outside_factory(home=None, *, tick=None, since=None) -> list[dict]:
    from lokay import store
    from lokay.measure import json_rows, ledger
    from lokay.replay import unpack

    home = HOME if home is None else home
    merged = [row for row in ledger(home) if row.get("kind") == "merged" and row.get("tick")
              and (tick is None or row["tick"] == tick)]
    keys = {(row["tick"], row.get("repo"), row.get("issue")) for row in merged}
    entered = set()
    directory = home / "ticks"
    paths = (*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz"))
    for row in json_rows(path for path in paths if keys and (since is None or path.name[:10] >= since)):
        key = (row.get("tick"), row.get("repo"), row.get("issue"))
        if row.get("kind") != "transition" or key not in keys:
            continue
        try:
            states = [unpack(row.get(field, {}), directory, source=directory) for field in ("before", "after")]
            if any(state.get("node") == "merge" for state in states):
                entered.add(key)
        except (OSError, ValueError, TypeError, AttributeError, EOFError):
            continue
    result = [{key: row.get(key) for key in ("repo", "issue", "sha", "tick")}
              for row in merged if (row["tick"], row.get("repo"), row.get("issue")) not in entered]
    path = home / "deploy.json"
    if path.exists():
        recorded = json.loads(path.read_text())
        current_files = store.deploy_fingerprint()["files"]
        recorded_files = recorded.get("files", {})
        for file in sorted(current_files.keys() | recorded_files.keys()):
            if file not in current_files or file not in recorded_files or current_files[file] != recorded_files[file]:
                result.append({"file": file, "head": recorded.get("head")})
    return result


def latest_needs_help() -> dict:
    from lokay.replay import unpack

    latest = None
    unreadable = 0
    directory = RUNS.parent / "ticks"
    for path in sorted((*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz")), reverse=True):
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
        if latest is not None:
            break
    return {"latest_needs_help": latest, "unreadable_records_or_files": unreadable}


STALL_RED_SECONDS = 48 * 3600
STALL_MERGE_SECONDS = 7 * 86400


def stalled_repos(home, now=None) -> list[dict]:
    from lokay.measure import ledger, report, timestamp

    now = datetime.now(timezone.utc).timestamp() if now is None else now
    entries = ledger(home)
    last_merge = {}
    for row in entries:
        stamp = timestamp(row.get("ts"))
        if row.get("kind") == "merged" and row.get("repo") and stamp is not None:
            last_merge[row["repo"]] = max(last_merge.get(row["repo"], 0), stamp.timestamp())
    result = []
    for repo, data in report(home)["red_main"].items():
        last = last_merge.get(repo)
        if data["hours"] <= STALL_RED_SECONDS / 3600:
            continue
        if last is not None and now - last < STALL_MERGE_SECONDS:
            continue
        result.append({"repo": repo, "hours": data["hours"], "picks": data["picks"],
                       "merges": sum(row.get("kind") == "merged" and row.get("repo") == repo
                                     and (stamp := timestamp(row.get("ts"))) is not None
                                     and now - stamp.timestamp() < STALL_MERGE_SECONDS for row in entries)})
    return result


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
    try:
        stalls = stalled_repos(HOME)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        stalls = []
        reasons.append(f"Stalled repo lookup failed: {exc}")
    for stall in stalls:
        reasons.append(f"{stall['repo']}: repo bez merge 7 dni i czerwony main ponad 48 h; "
                       f"red_main {stall['hours']:.1f} h; picks {stall['picks']}; merges 7d {stall['merges']}")
    repo = os.environ.get("LOKAY_ALARM_REPO", "mikolaj92/lokay")
    rows = gh_json(["issue", "list", "--repo", repo, "--state", "open",
                    "--search", "lokay-stalled in:title", "--limit", "1000000", "--json", "number,title,body"],
                   error="alarm lookup failed", strip=False, default="[]")
    alarms = [row for row in rows if stall_alarm(row)]
    evidence = "\n\n```json\n" + dumps(beat, indent=2) + "\n```"
    if not reasons:
        for alarm in alarms:
            gh_ok(["issue", "close", str(alarm["number"]), "--repo", repo,
                   "--comment", "Monitor recovered: no stall predicates remain." + evidence],
                  error="alarm closure failed", strip=False)
        return {"result": "ok", "closed": [alarm["number"] for alarm in alarms]}
    if not alarms:
        body = STALL_MARKER + "\n" + "\n".join(reasons) + evidence + "\n\n```json\n" + dumps(latest_needs_help(), indent=2) + "\n```"
        gh_ok(["issue", "create", "--repo", repo, "--title", STALL_TITLE, "--body", body],
              error="alarm creation failed", strip=False)
    return {"result": "stalled", "reasons": reasons}
