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
from lokay.github_yield import catalog_delivery
from lokay.delivery_receipt import parse_marker
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


class _Window:
    """Accumulate one time window without retaining source events."""

    def __init__(self, since: datetime) -> None:
        self.since = since
        self.by_repo: dict[str, Counter[str]] = defaultdict(Counter)
        self.semantic: dict[str, Counter[str]] = defaultdict(Counter)
        self.durations: dict[str, list[float]] = defaultdict(list)
        self.events = 0

    def add(self, row: dict[str, Any], traces: list[dict[str, Any]]) -> None:
        self.events += 1
        repo = str(row.get("repo") or "unknown")
        kind = str(row.get("kind") or "unknown")
        if kind == "issue_to_pr":
            self.by_repo[repo]["starts"] += 1
            if row.get("pr"):
                self.by_repo[repo]["prs"] += 1
            if not row.get("ok", False):
                self.by_repo[repo]["failures"] += 1
            reason = str(row.get("reason") or (row.get("error") or {}).get("code") or "")
            if reason:
                self.by_repo[repo][reason] += 1
        if kind == "pr_triage" and row.get("ok") and row.get("merged"):
            self.by_repo[repo]["merges"] += 1
        for trace in traces:
            skind = str(trace.get("kind") or "unknown")
            self.semantic[skind][f"{trace.get('source', 'unknown')}:{trace.get('status', 'unknown')}"] += 1
            if isinstance(trace.get("duration_ms"), (int, float)):
                self.durations[skind].append(float(trace["duration_ms"]))

    def report(self, path: Path) -> dict[str, Any]:
        return {
            "since": self.since.isoformat(),
            "state_path": str(path),
            "events": self.events,
            "by_repo": {repo: dict(counts) for repo, counts in sorted(self.by_repo.items())},
            "semantic": {
                kind: {
                    "outcomes": dict(counts),
                    "average_duration_ms": round(sum(self.durations[kind]) / len(self.durations[kind])) if self.durations[kind] else 0,
                }
                for kind, counts in sorted(self.semantic.items())
            },
            "note": "Local failures/traces come from state.jsonl; GitHub is the production source for merged delivery.",
        }


def build_reports(path: Path, *, windows: dict[str, datetime]) -> dict[str, dict[str, Any]]:
    """Read the complete history once for all windows; timestamps need not be ordered."""
    accumulators = {label: _Window(since) for label, since in windows.items()}
    if path.is_file() and accumulators:
        with path.open(encoding="utf-8", errors="ignore") as lines:
            for line in lines:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stamp = _ts(row.get("ts"))
                if stamp is None:
                    continue
                matching = [window for window in accumulators.values() if stamp >= window.since]
                if matching:
                    traces = list(_semantic_traces(row))
                    for window in matching:
                        window.add(row, traces)
    return {label: window.report(path) for label, window in accumulators.items()}


def build_report(path: Path, *, since: datetime) -> dict[str, Any]:
    return build_reports(path, windows={"single": since})["single"]


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
            def detector(body: str) -> str:
                try: return "autonomous" if parse_marker(body) else "unattributed"
                except (ValueError, json.JSONDecodeError): return "unattributed"
            report["delivery"] = catalog_delivery(
                runner(cfg), [repo.name for repo in cfg.active_repos()], since=since, hours=hours, receipt_detector=detector
            )
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc), kind="yield_report", **report))
    return emit_exit(ok(kind="yield_report", **report))


if __name__ == "__main__":
    raise SystemExit(main())
