"""Read-only JSON yield report from durable Lokay state events."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lokay.config import load_config
from lokay.envelope import emit_exit, err, ok
from lokay.github_yield import github_delivery
from lokay.proc._common import runner


def _ts(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _semantic_traces(value: Any):
    if isinstance(value, dict):
        trace = value.get("semantic")
        if isinstance(trace, dict) and trace.get("kind"):
            yield trace
        traces = value.get("semantic_traces")
        if isinstance(traces, list):
            for item in traces:
                if isinstance(item, dict) and item.get("kind"):
                    yield item
        for key, child in value.items():
            if key != "semantic_traces":
                yield from _semantic_traces(child)
    elif isinstance(value, list):
        for child in value:
            yield from _semantic_traces(child)


def build_report(path: Path, *, since: datetime) -> dict[str, Any]:
    by_repo: dict[str, Counter[str]] = defaultdict(Counter)
    semantic: dict[str, Counter[str]] = defaultdict(Counter)
    durations: dict[str, list[float]] = defaultdict(list)
    events = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            stamp = _ts(row.get("ts"))
            if stamp is None or stamp < since:
                continue
            events += 1
            repo = str(row.get("repo") or "unknown")
            kind = str(row.get("kind") or "unknown")
            if kind == "issue_to_pr":
                by_repo[repo]["starts"] += 1
                if row.get("pr"):
                    by_repo[repo]["prs"] += 1
                if row.get("merged") or row.get("mergedAt"):
                    by_repo[repo]["merges"] += 1
                if not row.get("ok", False):
                    by_repo[repo]["failures"] += 1
                reason = str(row.get("reason") or (row.get("error") or {}).get("code") or "")
                if reason:
                    by_repo[repo][reason] += 1
            # Factory actions (queue/intake) are not appended individually;
            # their durable pass workspace is summarized in state elsewhere.
            # Issue-to-PR embeds localize traces inside the Fala result.
            for trace in _semantic_traces(row):
                skind = str(trace.get("kind") or "unknown")
                semantic[skind][f"{trace.get('source', 'unknown')}:{trace.get('status', 'unknown')}"] += 1
                if isinstance(trace.get("duration_ms"), (int, float)):
                    durations[skind].append(float(trace["duration_ms"]))
    return {
        "since": since.isoformat(),
        "state_path": str(path),
        "events": events,
        "by_repo": {repo: dict(counts) for repo, counts in sorted(by_repo.items())},
        "semantic": {
            kind: {
                "outcomes": dict(counts),
                "average_duration_ms": round(sum(durations[kind]) / len(durations[kind])) if durations[kind] else 0,
            }
            for kind, counts in sorted(semantic.items())
        },
        "note": "Local failures/traces come from state.jsonl; GitHub is the production source for merged delivery.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-yield-report")
    p.add_argument("--config")
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--local-only", action="store_true")
    args = p.parse_args(argv)
    hours = max(0.0, args.hours)
    cfg = load_config(args.config)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    report = build_report(cfg.state_path, since=since)
    if not args.local_only:
        try:
            report["delivery"] = github_delivery(
                runner(cfg), cfg.incident_repo, since=since, hours=hours
            )
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc), kind="yield_report", **report))
    return emit_exit(ok(kind="yield_report", **report))


if __name__ == "__main__":
    raise SystemExit(main())
