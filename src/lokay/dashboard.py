"""Read-only factory dashboard; GitHub reads happen only in the refresh thread."""
from __future__ import annotations

from json import dumps
from lokay.store import write_json
from lokay.effects.gh import dashboard_request as gh

import argparse
import copy
import gzip
import html
import json
import os
import re
import shlex
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlsplit

import yaml

WARSAW = ZoneInfo("Europe/Warsaw")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
FORBIDDEN = ("key", "token", "secret", "auth", "password", "prompt", "body", "log")
HEARTBEAT_FIELDS = (
    "repo", "issue", "node", "node_since", "result", "time", "version", "failures",
    "last_error", "idle_reason", "issue_since", "last_merge", "main_status",
)
RUN_FIELDS = (
    "node", "branch", "pr", "result", "plan_rounds", "check_rounds", "fix_counts",
    "updated_at", "issue_title", "last_error",
)


def redact(value: str) -> str:
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+)", "[redacted]", value)
    value = re.sub(r"(?i)\b(?:bearer|basic)\s+\S+", "[redacted]", value)
    value = re.sub(r"(?i)\b\S*(?:key|token|secret|auth|password)\S*\s*[:=]\s*[^\s,;]+", "[redacted]", value)
    value = re.sub(r"https?://[^\s]+", "[url]", value)
    return value


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()
                if not any(word in str(k).lower() for word in FORBIDDEN)}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, str):
        return redact(value)
    return value if value is None or isinstance(value, (int, float, bool)) else None


def select(data: dict, fields: tuple) -> dict:
    return {k: safe(data[k]) for k in fields if k in data}


def read_json(path: Path) -> dict:
    try:
        if not path.exists() and path.with_suffix(".gz").exists():
            path = path.with_suffix(".gz")
        data = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def stamp(value) -> float:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0


def date(value) -> str:
    try:
        return datetime.fromtimestamp(stamp(value), WARSAW).strftime("%Y-%m-%d %H:%M") if stamp(value) else "—"
    except (ValueError, OverflowError, OSError):
        return "—"


def number(value) -> int:
    try:
        return max(0, int(value))
    except (ValueError, TypeError, OverflowError):
        return 0


def kind(files) -> str:
    if not isinstance(files, list) or not files:
        return "?"
    kinds = set()
    for item in files:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or not path:
            return "?"
        name = path.rsplit("/", 1)[-1]
        if path.startswith("docs/") or name.endswith((".md", ".rst", ".txt")) or name.startswith("LICENSE"):
            kinds.add("docs")
        elif path.startswith(("tests/", "test/", "fixtures/replay/")) or (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py") or name == "conftest.py":
            kinds.add("tests")
        else:
            kinds.add("code")
    return "code" if "code" in kinds else "docs+tests" if len(kinds) == 2 else kinds.pop()


def models() -> dict:
    names = ("LOKAY2_PROVIDER", "LOKAY2_MODEL")
    values = {name: os.environ[name] for name in names if os.environ.get(name)}
    if len(values) < 2:
        try:
            with (Path.home() / ".config/lokay/env").open() as stream:
                for line in stream:
                    match = re.match(r"^\s*export\s+(LOKAY2_PROVIDER|LOKAY2_MODEL)=(.*)$", line)
                    if match and match[1] not in values:
                        # Parse literals, never source the shell file or expand variables.
                        try:
                            parts = shlex.split(match[2], comments=True)
                            if len(parts) == 1:
                                values[match[1]] = parts[0]
                        except ValueError:
                            pass
        except OSError:
            pass
    return {"provider": redact(values.get(names[0], "—")), "model": redact(values.get(names[1], "—"))}


def enabled_repos(path: Path) -> list[str]:
    try:
        data = yaml.safe_load(path.read_text())
        entries = data.get("repos", []) if isinstance(data, dict) else []
        return sorted({entry["name"] for entry in entries if isinstance(entry, dict)
                       and entry.get("merge") == "on" and isinstance(entry.get("name"), str)
                       and REPO.fullmatch(entry["name"])})
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return []


def prs(data, merged: bool) -> list[dict]:
    if not isinstance(data, list):
        raise RuntimeError("gh returned an invalid PR list")
    output = []
    for item in data:
        if not isinstance(item, dict) or not str(item.get("headRefName", "")).startswith("lokay/"):
            continue
        fields = ("number", "title", "mergedAt", "createdAt", "headRefName", "additions", "deletions")
        pr = select(item, fields)
        if merged:
            pr["kind"] = kind(item.get("files"))
        elif item.get("kind") in ("docs", "tests", "docs+tests", "code", "?"):
            pr["kind"] = item["kind"]
        output.append(pr)
    return output


class Dashboard:
    def __init__(self):
        self.home = Path(os.environ.get("LOKAY_HOME", "~/.lokay")).expanduser()
        self.repos_file = Path(os.environ.get("LOKAY_REPOS_YAML", str(self.home / "host/repos.yaml"))).expanduser()
        self.cache_path = self.home / "dashboard-cache.json"
        cached = read_json(self.cache_path)
        self.cache = {"repos": {}, "last_refresh": stamp(cached.get("last_refresh")) or None,
                      "error": redact(str(cached.get("error") or "")) or None}
        for repo, item in cached.get("repos", {}).items() if isinstance(cached.get("repos"), dict) else []:
            if REPO.fullmatch(repo) and isinstance(item, dict):
                self.cache["repos"][repo] = {
                    "merged": prs(item["merged"] if isinstance(item.get("merged"), list) else [], False),
                    "open": prs(item["open"] if isinstance(item.get("open"), list) else [], False),
                    "open_issues": number(item["open_issues"]) if item.get("open_issues") is not None else None,
                    "last_refresh": item.get("last_refresh"),
                    "error": redact(str(item.get("error") or "")),
                }
        self.cache["pr_details"] = {}
        for key, item in cached.get("pr_details", {}).items() if isinstance(cached.get("pr_details"), dict) else []:
            repo, _, pr_number = key.rpartition("#")
            if REPO.fullmatch(repo) and pr_number.isdigit() and isinstance(item, dict):
                self.cache["pr_details"][key] = select(item, ("additions", "deletions", "files"))
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def persist(self):
        with self.lock:
            data = copy.deepcopy(self.cache)
        try:
            write_json(self.cache_path, data, ensure_ascii=False)
        except OSError:
            with self.lock:
                self.cache["error"] = "Could not save dashboard cache"

    def refresh(self):
        repos = enabled_repos(self.repos_file)
        try:
            limits = gh("api", "rate_limit")
            if number(limits["resources"]["core"]["remaining"]) < 200:
                raise RuntimeError("Refresh skipped: core rate limit remaining < 200")
        except (RuntimeError, KeyError, TypeError) as error:
            with self.lock:
                self.cache["error"] = redact(str(error))
                for repo in repos:
                    self.cache["repos"].setdefault(repo, {})["error"] = redact(str(error))
            self.persist()
            return
        for index, repo in enumerate(repos):
            if index and self.stop.wait(1):
                return
            try:
                merged_data = gh("pr", "list", "-R", repo, "--state", "merged", "--search", "head:lokay/", "--limit", "100", "--json", "number,title,url,mergedAt,headRefName,additions,deletions,files")
                if not isinstance(merged_data, list):
                    raise RuntimeError("gh returned an invalid PR list")
                for pr in merged_data:
                    if not isinstance(pr, dict) or not str(pr.get("headRefName", "")).startswith("lokay/"):
                        continue
                    key = f'{repo}#{number(pr.get("number"))}'
                    with self.lock:
                        details = self.cache["pr_details"].get(key)
                    if details is None and (not pr.get("files") or number(pr.get("additions")) + number(pr.get("deletions")) == 0):
                        details = gh("pr", "view", str(number(pr.get("number"))), "-R", repo, "--json", "additions,deletions,files")
                        if not isinstance(details, dict):
                            raise RuntimeError("gh returned invalid PR details")
                        details = select(details, ("additions", "deletions", "files"))
                        with self.lock:
                            self.cache["pr_details"][key] = details
                    if details is not None:
                        pr.update(details)
                merged = prs(merged_data, True)
                opened = prs(gh("pr", "list", "-R", repo, "--state", "open", "--limit", "100", "--json", "number,title,url,createdAt,headRefName,additions,deletions"), False)
                issues = gh("issue", "list", "-R", repo, "--state", "open", "--limit", "1000", "--json", "number")
                if not isinstance(issues, list):
                    raise RuntimeError("gh returned an invalid issue list")
                item = {"merged": merged, "open": opened, "open_issues": len(issues), "last_refresh": time.time(), "error": None}
                with self.lock:
                    self.cache["repos"][repo] = item
            except RuntimeError as error:
                with self.lock:
                    self.cache["repos"].setdefault(repo, {})["error"] = redact(str(error))
        with self.lock:
            self.cache["last_refresh"] = time.time()
            self.cache["error"] = None
        self.persist()

    def worker(self):
        interval = max(1, number(os.environ.get("LOKAY_DASHBOARD_REFRESH", "300")) or 300)
        while not self.stop.is_set():
            self.refresh()
            self.stop.wait(interval)

    def ticks(self, offset: int = 0, day: str = "") -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        offset = offset if not day or day == today else 0
        lines = []
        path = self.home / "ticks" / f"{today}.jsonl"
        try:
            with path.open("rb") as stream:
                if offset > path.stat().st_size:
                    offset = 0
                stream.seek(offset)
                for _ in range(200):
                    line = stream.readline()
                    if not line.endswith(b"\n"):
                        break
                    offset = stream.tell()
                    try:
                        row = json.loads(line)
                        for key in ("before", "after", "output"):
                            value = row.get(key)
                            if isinstance(value, dict) and re.fullmatch(r"sha256:[a-f0-9]{64}", str(value.get("blob", ""))):
                                row[key] = read_json(self.home / "ticks" / "blobs" / value["blob"][7:])
                        lines.append(safe(row))
                    except (ValueError, TypeError):
                        continue
        except OSError:
            pass
        return {"date": today, "offset": offset, "lines": lines}

    def state(self) -> dict:
        now = time.time()
        heartbeat = select(read_json(self.home / "heartbeat.json"), HEARTBEAT_FIELDS)
        repo, issue = heartbeat.get("repo"), str(heartbeat.get("issue", ""))
        current_path = None
        if isinstance(repo, str) and REPO.fullmatch(repo) and issue.isdigit():
            current_path = self.home / "runs" / repo.replace("/", "__") / issue / "state.json"
        current = select(read_json(current_path), RUN_FIELDS) if current_path else {}
        paths = []
        for path in (self.home / "runs").glob("*/*/state.json"):
            try:
                paths.append((path.stat().st_mtime, str(path), path))
            except OSError:
                pass
        current_label = None
        if current_path is None and (repo is None or heartbeat.get("issue") is None) and paths:
            current_path = max(paths)[2]
            current = select(read_json(current_path), RUN_FIELDS)
            current.update(repo=current_path.parent.parent.name.replace("__", "/"), issue=current_path.parent.name)
            current_label = "last active run (heartbeat idle)"
        recent = []
        for _, _, path in sorted(paths, reverse=True)[:10]:
            data = current if path == current_path else select(read_json(path), RUN_FIELDS)
            recent.append({"repo": path.parent.parent.name.replace("__", "/"), "issue": path.parent.name, **data})
        with self.lock:
            cache = copy.deepcopy(self.cache)
        from lokay.store import main_status

        statuses = main_status(self.home)
        merged, opened, per_repo = [], [], []
        for name in enabled_repos(self.repos_file):
            item = cache["repos"].get(name, {})
            merges = [{**pr, "repo": name} for pr in item.get("merged", [])]
            opens = [{**pr, "repo": name} for pr in item.get("open", [])]
            merged.extend(merges)
            opened.extend(opens)
            last = max(merges, key=lambda pr: stamp(pr.get("mergedAt")), default={})
            count24 = sum(now - 86400 <= stamp(pr.get("mergedAt")) <= now for pr in merges)
            count7 = sum(now - 7 * 86400 <= stamp(pr.get("mergedAt")) <= now for pr in merges)
            issues = item.get("open_issues")
            per_repo.append({"repo": name, "main_status": safe(statuses.get(name)), "open_issues": issues, "open_prs": len(opens) if issues is not None else None,
                             "last_merge": last, "merges24": count24, "merges7": count7,
                             "last_refresh": item.get("last_refresh"), "error": item.get("error"),
                             "eta24": eta(issues, count24 / 24, now), "eta7": eta(issues, count7 / 168, now)})
        merged.sort(key=lambda pr: (stamp(pr.get("mergedAt")), pr["repo"], number(pr.get("number"))), reverse=True)
        total_issues = sum(number(r["open_issues"]) for r in per_repo) if all(r["open_issues"] is not None for r in per_repo) else None
        return {"now": now, "heartbeat": heartbeat, "current": current, "current_label": current_label, "recent": recent, **models(),
                "last_refresh": cache["last_refresh"], "error": cache["error"], "merged": merged[:100],
                "growth_days": buckets(merged, opened, now, False), "growth_hours": buckets(merged, opened, now, True),
                "open_prs": len(opened), "repos": per_repo,
                "total": {"open_issues": total_issues,
                          "eta24": eta(total_issues, sum(r["merges24"] for r in per_repo) / 24, now),
                          "eta7": eta(total_issues, sum(r["merges7"] for r in per_repo) / 168, now)}}


def eta(issues, rate: float, now: float) -> dict:
    if issues is None:
        return {"text": "unavailable", "date": "—"}
    if not rate:
        return {"text": "no merges in window", "date": "—"}
    hours = number(issues) / rate
    return {"text": f"{hours / 24:.1f} days" if hours >= 24 else f"{hours:.1f} hours", "date": date(now + hours * 3600)}


def buckets(merged: list, opened: list, now: float, hourly: bool) -> list[dict]:
    local = datetime.fromtimestamp(now, WARSAW)
    # Hour windows use real elapsed hours, including both occurrences at DST fall-back.
    end = local.replace(minute=0, second=0, microsecond=0) if hourly else local.replace(hour=0, minute=0, second=0, microsecond=0)
    output = []
    for offset in reversed(range(24 if hourly else 14)):
        if hourly:
            start_ts = end.timestamp() - offset * 3600
            finish_ts = start_ts + 3600
        else:
            start = end - timedelta(days=offset)
            start_ts, finish_ts = start.timestamp(), (start + timedelta(days=1)).timestamp()
        matches = [pr for pr in merged if start_ts <= stamp(pr.get("mergedAt")) < finish_ts]
        output.append({"bucket": date(start_ts), "merges": len(matches),
                       "additions": sum(number(pr.get("additions")) for pr in matches),
                       "deletions": sum(number(pr.get("deletions")) for pr in matches),
                       "opened": sum(start_ts <= stamp(pr.get("createdAt")) < finish_ts for pr in opened)})
    return output


def esc(value) -> str:
    return html.escape(str(value if value is not None else "—"), quote=True)


def link(repo, pr) -> str:
    if not isinstance(repo, str) or not REPO.fullmatch(repo) or not number(pr):
        return "—"
    return f'<a href="{esc(f"https://github.com/{repo}/pull/{number(pr)}")}">#{number(pr)}</a>'


def table(headers, rows) -> str:
    return '<div class="scroll"><table><thead><tr>' + "".join(f"<th>{esc(h)}</th>" for h in headers) + '</tr></thead><tbody>' + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) + '</tbody></table></div>'


def rounds(run) -> str:
    return esc(f'Plan {run.get("plan_rounds", "—")} / Check {run.get("check_rounds", "—")} / Fix {run.get("fix_counts", "—")}')


def duration(seconds: float) -> str:
    return f"{max(0, seconds) / 60:.1f} min" if seconds >= 60 else f"{max(0, seconds):.0f} s"


def render(data: dict) -> str:
    hb, run, now = data["heartbeat"], data["current"], data["now"]
    age = now - stamp(hb.get("time")) if stamp(hb.get("time")) else None
    since = stamp(hb.get("node_since"))
    active = run if data.get("current_label") else hb
    fields = [("Repo", esc(active.get("repo"))), ("Issue", esc(active.get("issue"))),
              ("PR", link(active.get("repo"), run.get("pr"))),
              ("Node", esc(str(active.get("node") or run.get("node") or "—").capitalize())),
              ("Round", rounds(run)), ("Result", esc(hb.get("result"))),
              ("Time in node", esc(duration(now - since) if since else "—")),
              ("Heartbeat age", f'<span class="{"bad" if age is None or age > 900 else ""}">{esc(duration(age) if age is not None else "missing")}</span>'),
              ("Failures", esc(hb.get("failures"))),
              ("Last error", esc(str(hb.get("last_error") or run.get("last_error") or "")[:300])),
              ("Idle reason", esc(hb.get("idle_reason"))), ("Version", esc(str(hb.get("version") or "—")[:12])),
              ("Provider / model", esc(f'{data["provider"]} / {data["model"]}'))]
    body = '<h1>Lokay2 factory</h1><h2>Current state</h2>'
    if data.get("current_label"):
        body += f'<p>{esc(data["current_label"])}</p>'
    body += table(["Field", "Value"], fields)
    body += ('<h2>Live ticks</h2><ol id="ticks" aria-live="polite"></ol>'
             '<button id="tick-back" type="button">Previous seq</button> '
             '<button id="tick-live" type="button">Live</button><pre id="tick-state"></pre>')
    body += f'<p>Last GitHub refresh: {esc(date(data["last_refresh"]))}. {esc(data["error"] or "")}</p>'
    body += '<h2>Finished lokay/* merges</h2>' + table(["Merged (Warsaw)", "Repo", "PR", "Title", "+ / −", "Kind"], [
        [esc(date(pr.get("mergedAt"))), esc(pr["repo"]), link(pr["repo"], pr.get("number")), esc(pr.get("title")),
         esc(f'+{number(pr.get("additions"))} / −{number(pr.get("deletions"))}'), esc(pr.get("kind", "?"))] for pr in data["merged"]])
    body += f'<h2>Growth</h2><p>Current open lokay/* PRs: {esc(data["open_prs"])}</p>'
    for key, title in (("growth_days", "Last 14 days"), ("growth_hours", "Last 24 hours")):
        maximum = max((bucket["merges"] for bucket in data[key]), default=1) or 1
        body += f'<h3>{title}</h3>' + table(["Bucket (Warsaw)", "Merges", "Lines +", "Lines −", "Open PRs created", "Merges"], [
            [esc(bucket["bucket"]), esc(bucket["merges"]), esc(bucket["additions"]), esc(bucket["deletions"]), esc(bucket["opened"]),
             f'<div class="bar" style="width:{bucket["merges"] / maximum * 100:.1f}%"></div>'] for bucket in data[key]])
    body += '<h2>Per repo (merge on)</h2>' + table(["Repo", "Open issues", "Open lokay PRs", "Last merge", "PR", "24h", "7d", "Refresh", "Error"], [
        [esc(r["repo"]), esc(r["open_issues"]), esc(r["open_prs"]), esc(date(r["last_merge"].get("mergedAt"))),
         link(r["repo"], r["last_merge"].get("number")), esc(r["merges24"]), esc(r["merges7"]), esc(date(r["last_refresh"])), esc(r["error"])] for r in data["repos"]])
    body += '<h2>Main status</h2>' + table(["Repo", "Status", "Since", "Culprit SHA", "PR", "Issue"], [
        [esc(r["repo"]), esc((r.get("main_status") or {}).get("status")),
         esc(date((r.get("main_status") or {}).get("since"))),
         esc(((r.get("main_status") or {}).get("culprit") or {}).get("sha")),
         link(r["repo"], ((r.get("main_status") or {}).get("culprit") or {}).get("pr")),
         esc((r.get("main_status") or {}).get("issue"))] for r in data["repos"]])
    body += '<h2>ETA</h2><p>ETA = open issues / merge rate; rate24 = merges in last 24h / 24h; rate7 = merges in last 7d / 7 days; total uses summed open issues and summed rates.</p>'
    body += table(["Repo", "Open issues", "ETA (24h rate)", "Date (Warsaw)", "ETA (7d rate)", "Date (Warsaw)"], [
        [esc(r["repo"]), esc(r["open_issues"]), esc(r["eta24"]["text"]), esc(r["eta24"]["date"]), esc(r["eta7"]["text"]), esc(r["eta7"]["date"])]
        for r in [*data["repos"], {"repo": "Total", **data["total"]}]])
    body += '<h2>Recent runs</h2>' + table(["Repo", "Issue", "PR", "Node", "Rounds", "Updated (Warsaw)"], [
        [esc(r["repo"]), esc(r["issue"]), link(r["repo"], r.get("pr")), esc(str(r.get("node") or "—").capitalize()), rounds(r), esc(date(r.get("updated_at")))] for r in data["recent"]])
    body += '<p>GitHub lists are capped: 100 merged PRs and 100 open PRs per repo, 1000 open issues per repo. Rates and ETA use this cached sample; unavailable counts are shown as —. Only currently open PRs contribute to growth opened counts.</p>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Lokay2 dashboard</title><style>body{font:14px system-ui,sans-serif;color:#17212b;background:#f5f7fa;margin:24px}h1{font-size:24px}h2{margin-top:28px;font-size:19px}h3{font-size:15px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:6px 9px;border-bottom:1px solid #dce2e8;vertical-align:top;overflow-wrap:anywhere}th{background:#e7edf3}tr:nth-child(even){background:#f8fafc}a{color:#1262a4}.bad{color:#b00020;font-weight:bold}.bar{background:#337ab7;height:12px;min-width:0}p{color:#485563}</style></head><body>' + body + '''<script>
let offset=0, day='', events=[], selected=null;
const list=document.getElementById('ticks'), state=document.getElementById('tick-state');
function show(event){
  selected=event;
  state.textContent=JSON.stringify({tick:event.tick,seq:event.seq,state:event.after||event.output},null,2);
}
document.getElementById('tick-back').onclick=()=>{
  const current=selected||events.at(-1);
  if(!current)return;
  const previous=events.findLast(e=>e.tick===current.tick&&e.seq<current.seq&&e.kind==='transition');
  if(previous)show(previous);
  else state.textContent=JSON.stringify({tick:current.tick,seq:current.seq,state:current.before},null,2);
};
document.getElementById('tick-live').onclick=()=>{selected=null;state.textContent='';};
async function tail(){
  try{
    const response=await fetch('/api/ticks.json?offset='+offset+'&date='+day);
    if(!response.ok)return;
    const data=await response.json();
    if(day&&day!==data.date){events=[];list.replaceChildren();selected=null;}
    day=data.date;offset=data.offset;
    for(const event of data.lines){
      events.push(event);
      const item=document.createElement('li'), button=document.createElement('button');
      button.type='button';
      button.textContent=event.tick.slice(0,8)+' #'+event.seq+' '+event.repo+' #'+event.issue+' '+event.node+' '+(event.event||event.call);
      button.onclick=()=>show(event);item.append(button);list.append(item);
    }
    while(list.children.length>20)list.firstChild.remove();
  }catch{}
}
tail();setInterval(tail,2000);
</script></body></html>'''


def handler(dashboard: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                content, mime, status = b"ok\n", "text/plain", 200
            elif path == "/api/ticks.json":
                query = parse_qs(urlsplit(self.path).query)
                data = dashboard.ticks(number(query.get("offset", [0])[0]), query.get("date", [""])[0])
                content, mime, status = dumps(data, ensure_ascii=False).encode(), "application/json", 200
            elif path in ("/", "/api/state.json"):
                data = dashboard.state()
                if path == "/":
                    content, mime = render(data).encode(), "text/html"
                else:
                    content, mime = dumps(data, ensure_ascii=False).encode(), "application/json"
                status = 200
            else:
                content, mime, status = b"not found\n", "text/plain", 404
            self.send_response(status)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format, *args):
            # Request paths may contain secrets; omit access logging.
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    dashboard = Dashboard()
    server = ThreadingHTTPServer((args.host, args.port), handler(dashboard))
    threading.Thread(target=dashboard.worker, daemon=True, name="dashboard-refresh").start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
