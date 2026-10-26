from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lokay import config, store
from lokay.effects.gh import gh_json
from lokay.dashboard import kind
from lokay.effects.git import commit_time, merge_files
from lokay.replay import unpack


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("expected an ISO-8601 UTC time")
    return parsed


def boundary(value: str) -> datetime:
    if re.match(r"^\d{4}-\d\d-\d\d", value):
        return utc(value)
    return datetime.fromisoformat(commit_time(Path(__file__).resolve().parents[2], value)).astimezone(timezone.utc)


def changed_files(value, home: Path):
    value = unpack(value, home)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("files", "changed_files"):
            files = value.get(key)
            if isinstance(files, list) and not files:
                return []
            if isinstance(files, list):
                normalized = [{"path": item} if isinstance(item, str) else item for item in files]
                if kind(normalized) != "?":
                    return normalized
        for child in value.values():
            found = changed_files(child, home)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = changed_files(child, home)
            if found is not None:
                return found
    return None


def merges(home: Path, ticks: list[datetime] | None = None) -> list[dict]:
    rows = []
    for path in sorted((home / "ticks").glob("*.jsonl*")):
        if not path.name.endswith((".jsonl", ".jsonl.gz")):
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("expected tick object")
                if ticks is not None:
                    ticks.append(utc(row["ts"]))
                if row.get("kind") in ("call", "transition") and row.get("repo") and row.get("issue"):
                    rows.append((utc(row["ts"]), row))
    evidence = {}
    repos = None
    seen = set()
    result = []
    for timestamp, row in sorted(rows, key=lambda item: item[0]):
        key = (row["repo"], row["issue"])
        files = changed_files({name: row[name] for name in ("output", "before", "after", "event") if name in row}, home)
        if files is not None:
            evidence[key] = files
        if row["kind"] != "transition" or row.get("node") != "merge":
            continue
        event = unpack(row.get("event"), home)
        fields = event.get("fields", {}) if isinstance(event, dict) else {}
        if not isinstance(fields, dict) or fields.get("result") != "merged":
            continue
        sha = fields.get("sha")
        if not isinstance(sha, str) or not sha.strip() or key in seen:
            continue
        files = evidence.get(key)
        if repos is None:
            repos = {repo["name"]: Path(repo["clone_path"]).expanduser() for repo in config.load_repos()}
        clone = repos.get(row["repo"])
        if clone is not None:
            merged_files = merge_files(clone, sha)
            if merged_files is not None:
                files = merged_files
        if files == []:
            continue
        seen.add(key)
        change = kind(files)
        result.append({"time": timestamp, "kind": "code" if change not in ("docs", "lokay") else change,
                       "unknown_kind": change == "?"})
    return result


def window(label: str, start: datetime, end: datetime, records: list[dict]) -> dict:
    hours = (end - start).total_seconds() / 3600
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("window end must be after its start")
    selected = [row for row in records if start <= row["time"] < end]
    code = sum(row["kind"] == "code" for row in selected)
    docs = sum(row["kind"] == "docs" for row in selected)
    return {"label": label, "start": start.isoformat(), "until": end.isoformat(), "hours": hours,
            "code": code, "docs": docs, "code/h": code / hours, "docs/h": docs / hours,
            "unknown_kind": sum(row["unknown_kind"] for row in selected)}


def segment(name: str, data: dict) -> str:
    text = (f"{name}={data['label']} code/h={data['code/h']:.2f} docs/h={data['docs/h']:.2f} "
            f"n={data['code']}/{data['docs']} hours={data['hours']:g}")
    return text + (f" unknown_kind={data['unknown_kind']}" if data["unknown_kind"] else "")


def timestamp(value):
    try:
        return utc(value) if isinstance(value, str) else None
    except ValueError:
        return None


def json_rows(paths):
    for path in paths:
        try:
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        if isinstance(row, dict):
                            yield row
                    except ValueError:
                        continue
        except (OSError, EOFError, UnicodeError):
            continue


def ledger(home: Path) -> list[dict]:
    return list(json_rows([home / "ledger.jsonl"]))


MATURED_THRESHOLD = 20


def record_merge(repo, issue, pr, sha, files, main=None):
    picked = None
    for row in ledger(store.RUNS.parent):
        if (row.get("repo"), row.get("issue")) == (repo, issue):
            if row.get("kind") == "merged":
                picked = None
            elif row.get("kind") == "pick" and picked is None and timestamp(row.get("ts")):
                picked = row["ts"]
    state = store.state_read(repo, issue)
    paths = (path for path in (store.RUNS.parent / "ticks").glob("*.jsonl*")
             if picked and re.fullmatch(r"\d{4}-\d\d-\d\d\.jsonl(?:\.gz)?", path.name)
             and path.name[:10] >= picked[:10])
    pi_ms = tokens_in = tokens_out = None
    cost_source = "none"
    if picked:
        pi_ms = 0
        since = timestamp(picked)
        reported = 0
        missing = False
        for row in json_rows(paths):
            if row.get("call") != "pi" or (row.get("repo"), row.get("issue")) != (repo, issue):
                continue
            when = timestamp(row.get("ts"))
            if when is None or since is None or when < since:
                continue
            if isinstance(row.get("ms"), (int, float)):
                pi_ms += row["ms"]
            usage = row.get("usage")
            if isinstance(usage, dict) and isinstance(usage.get("tokens_in"), (int, float)) \
                    and isinstance(usage.get("tokens_out"), (int, float)):
                tokens_in = (tokens_in or 0) + usage["tokens_in"]
                tokens_out = (tokens_out or 0) + usage["tokens_out"]
                reported += 1
            else:
                missing = True
        if reported and not missing:
            cost_source = "pi"
        else:
            tokens_in = tokens_out = None
    ci = state.get("local_ci") if isinstance(state.get("local_ci"), dict) else {}
    store.ledger_append({"kind": "merged", "repo": repo, "issue": issue, "pr": pr, "sha": sha,
                         "picked_at": picked, "attempt": state.get("last_attempt"), "pi_ms": pi_ms,
                         "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_source": cost_source,
                         "fix_rounds": state.get("check_rounds"),
                         "executed": main["baseline"]["ci"].get("executed", 0) if isinstance(main, dict) else 0,
                         "checks_source": "gh" if ci.get("ci") in ("green", "inherited")
                         else "local" if ci.get("tested") is True else "none",
                         "main": {"status": main["status"], "executed": main["baseline"]["ci"].get("executed", 0),
                                  "lock": main["baseline"]["lockfile"]["status"]} if isinstance(main, dict) else None,
                         "change_kind": kind([{"path": path} if isinstance(path, str) else path for path in files]) if files else None})


def matured(home):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    return [row for row in ledger(home) if row.get("kind") == "merged"
            and timestamp(row.get("ts")) and timestamp(row["ts"]) <= cutoff]


def escapes(home) -> list[dict]:
    try:
        with store.shared_file_lock(home / "escape.lock"):
            checks = [row for row in ledger(home) if row.get("kind") == "escape_check"]
            checked = {row.get("sha") for row in checks}
            for row in matured(home):
                repo, issue, sha = row.get("repo"), row.get("issue"), row.get("sha")
                if not repo or not issue or not sha or sha in checked:
                    continue
                try:
                    state = gh_json(["issue", "view", str(issue), "--repo", repo, "--json", "state,stateReason"],
                                    error="escape issue lookup failed")
                    commits = gh_json(["api", f"repos/{repo}/commits?sha=main&since={row['ts']}",
                                       "--paginate", "--slurp"], error="escape revert lookup failed")
                    why = ["issue reopened"] if state["state"] == "OPEN" else []
                    if (store.main_status(home).get(repo, {}).get("culprit") or {}).get("sha") == sha:
                        why.append("main red")
                    if any(f"This reverts commit {sha}" in item.get("commit", {}).get("message", "")
                           for page in commits for item in page):
                        why.append("reverted")
                    check = {key: row.get(key) for key in ("repo", "issue", "pr", "sha")} | {"kind": "escape_check", "why": why}
                    store.ledger_append(check)
                    checks.append(check)
                    checked.add(sha)
                except Exception:
                    continue
            return [{key: row.get(key) for key in ("repo", "issue", "pr", "sha", "why")}
                    for row in checks if row.get("why")]
    except Exception:
        return []


def report(home):
    entries = ledger(home)
    red_main = {}
    for repo, status in store.main_status(home).items():
        if status.get("status") == "red":
            since = datetime.fromtimestamp(status["since"], timezone.utc)
            red_main[repo] = {"hours": (datetime.now(timezone.utc) - since).total_seconds() / 3600,
                              "picks": sum(row.get("kind") == "pick" and row.get("reason") == "red_main"
                                           and row.get("repo") == repo and timestamp(row.get("ts")) is not None
                                           and timestamp(row["ts"]) >= since for row in entries)}
    rows = [row for row in entries if row.get("kind") == "merged"]
    days = {}
    counts = {}
    for row in rows:
        day = (row.get("ts") or "unknown")[:10]
        days[day] = days.get(day, 0) + 1
        change = row.get("change_kind") or "unknown"
        counts[change] = counts.get(change, 0) + 1
    readiness, regressions = {}, []
    recorded = 0
    for row in rows:
        main = row.get("main")
        if main is None:
            continue
        recorded += 1
        previous = readiness.get(row["repo"])
        if previous is not None:
            why = ([f"status green->{main['status']}"] if previous["status"] == "green" and main["status"] in ("red", "unknown") else [])
            if main["executed"] < previous["executed"]:
                why.append(f"executed {previous['executed']}->{main['executed']}")
            if previous["lock"] == "pass" and main["lock"] == "fail":
                why.append("lock pass->fail")
            if why:
                regressions.append({key: row.get(key) for key in ("repo", "issue", "pr", "sha")} | {"why": why})
        readiness[row["repo"]] = main
    closed = {}
    for path in (home / "runs").glob("*/[0-9]*/state.json"):
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(state, dict) or state.get("result") != "closed":
            continue
        repo = path.parent.parent.name.replace("__", "/")
        reason = state.get("reason") or "unknown"
        closed.setdefault(repo, {})
        closed[repo][reason] = closed[repo].get(reason, 0) + 1
    durations = sorted((utc(row["ts"]) - utc(row["picked_at"])).total_seconds() / 60
                       for row in rows if timestamp(row.get("picked_at")) and timestamp(row.get("ts")))
    def mean(field, divisor=1):
        values = [row[field] / divisor for row in rows if isinstance(row.get(field), (int, float))]
        return sum(values) / len(values) if values else None
    matured_rows = matured(home)
    escape_rate = f"{len(escapes(home))}/{len(matured_rows)}"
    token_rows = [row for row in rows if row.get("cost_source") == "pi"]
    def token_mean(field):
        values = [row[field] for row in token_rows if isinstance(row.get(field), (int, float))]
        return sum(values) / len(values) if values else None
    return {"blocked_pick_errors": sum(row.get("kind") == "pick" and any(result != "merged" for result in row.get("blocked_by", {}).values()) for row in entries),
            "red_main": red_main,
            "red_main_errors": [repo for repo, row in red_main.items() if row["hours"] > 2 and not row["picks"]],
            "merges_per_day": days, "change_counts": counts, "mean_fix_rounds": mean("fix_rounds"),
            "pi_minutes_per_merge": mean("pi_ms", 60000),
            "tokens_in_per_merge": token_mean("tokens_in"),
            "tokens_out_per_merge": token_mean("tokens_out"),
            "pick_to_merge_p50_minutes": durations[math.ceil(len(durations) * .5) - 1] if durations else None,
            "pick_to_merge_p90_minutes": durations[math.ceil(len(durations) * .9) - 1] if durations else None,
            "readiness": readiness, "readiness_regressions": regressions, "readiness_recorded": f"{recorded}/{len(rows)}",
            "escape_rate_48h": escape_rate + (" (za mało danych)" if len(matured_rows) < MATURED_THRESHOLD else ""),
            "closed": closed}


def daily(home: Path, days: int) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(days))]
    counts = {day: {"date": day, "has_ticks": False, "merges": None, "failed_reasons": None,
                    "idle": None, "pick_to_merge_p50_minutes": None, "pick_to_merge_p90_minutes": None}
              for day in dates}
    failures = {day: Counter() for day in dates}
    for path in sorted((home / "ticks").glob("*.jsonl*")):
        if not re.fullmatch(r"\d{4}-\d\d-\d\d\.jsonl(?:\.gz)?", path.name) or path.name[:10] not in counts:
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                day = utc(row["ts"]).date().isoformat()
                if day not in counts:
                    continue
                data = counts[day]
                if not data["has_ticks"]:
                    data.update(has_ticks=True, merges=0, idle=dict.fromkeys(("host_down", "pi_capacity", "disk"), 0))
                if row.get("kind") == "idle" and row.get("reason") in data["idle"]:
                    data["idle"][row["reason"]] += 1
                if row.get("kind") != "transition":
                    continue
                before, after, event = (unpack(row.get(key, {}), home) for key in ("before", "after", "event"))
                if not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(event, dict):
                    raise ValueError("missing transition data")
                outcome = event.get("outcome") or {}
                fields = event.get("fields") or {}
                result = fields.get("result") or outcome.get("result") or after.get("result")
                if result == "merged" and before.get("result") != "merged":
                    data["merges"] += 1
                if result == "failed" and (fields.get("result") == "failed" or outcome.get("result") == "failed"
                                           or (before.get("result"), before.get("reason")) != (after.get("result"), after.get("reason"))):
                    reason = fields.get("reason") or outcome.get("reason") or after.get("reason") or "unknown"
                    failures[day][reason] += 1
    durations = {day: [] for day in dates}
    for row in ledger(home):
        merged, picked = timestamp(row.get("ts")), timestamp(row.get("picked_at"))
        if row.get("kind") == "merged" and merged and picked and merged >= picked:
            day = merged.date().isoformat()
            if day in durations:
                durations[day].append((merged - picked).total_seconds() / 60)
    for day, data in counts.items():
        if data["has_ticks"]:
            data["failed_reasons"] = [{"reason": reason, "count": count}
                                      for reason, count in sorted(failures[day].items(), key=lambda item: (-item[1], item[0]))[:5]]
        values = sorted(durations[day])
        for percentile in (50, 90):
            data[f"pick_to_merge_p{percentile}_minutes"] = values[math.ceil(len(values) * percentile / 100) - 1] if values else None
    return list(counts.values())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lokay measure")
    parser.add_argument("--baseline")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--baseline-until")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--daily", action="store_true", help="daily UTC report from local ticks and ledger")
    parser.add_argument("--days", type=int, help="number of UTC days including today (default: 7)")
    args = parser.parse_args(argv)
    if args.days is not None and (not args.daily or args.days <= 0):
        parser.error("--days requires --daily and a positive number")
    if args.daily and any((args.baseline, args.since, args.until, args.baseline_until)):
        parser.error("--daily cannot be combined with window options")
    if args.baseline and not args.since:
        parser.error("--since is required with --baseline")
    try:
        if args.daily:
            data = daily(config.HOME, args.days if args.days is not None else 7)
            if args.json:
                print(json.dumps(data))
            else:
                for row in data:
                    ticks = (f"merges={row['merges']} failed_reasons={row['failed_reasons']} idle={row['idle']}"
                             if row["has_ticks"] else "brak danych")
                    p50, p90 = (row[f"pick_to_merge_p{percentile}_minutes"] for percentile in (50, 90))
                    print(f"{row['date']} UTC | {ticks} | pick→merge p50={p50} p90={p90} min")
            return 0
        if not args.baseline:
            data = report(config.HOME)
            text = " | ".join(f"{key}={'brak danych' if value is None and key.startswith('tokens_') else value}"
                              for key, value in data.items())
            print(json.dumps(data) if args.json else "measure " + text)
            return 1 if data["red_main_errors"] or data["blocked_pick_errors"] else 0
        start_a, start_b = boundary(args.baseline), boundary(args.since)
        end_a = boundary(args.baseline_until) if args.baseline_until else start_b
        end_b = boundary(args.until) if args.until else datetime.now(timezone.utc)
        window(args.baseline, start_a, end_a, [])
        window(args.since, start_b, end_b, [])
        ticks = []
        records = merges(config.HOME, ticks)
        for name, start, end in (("A", start_a, end_a), ("B", start_b, end_b)):
            if not any(start <= timestamp < end for timestamp in ticks):
                raise ValueError(f"no ticks for window {name} {start.isoformat()}..{end.isoformat()}")
        a = window(args.baseline, start_a, end_a, records)
        b = window(args.since, start_b, end_b, records)
        verdict = "keep" if b["code/h"] >= a["code/h"] else "revert"
        print(json.dumps({"A": a, "B": b, "verdict": verdict}) if args.json else
              f"measure {segment('A', a)} | {segment('B', b)} | verdict={verdict}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"measure: {exc}", file=sys.stderr)
        return 2
