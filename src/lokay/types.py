from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

IssueKind: TypeAlias = Literal["code", "docs_change"]

PLAN_RESET = {
    "plan_phase": "write",
    "plan_branches": {},
    "plan_synthesis": {},
    "plan_accepted_sha": None,
}


def pr_number(value):
    if isinstance(value, str) and (match := re.fullmatch(r"https://github\.com/[^/]+/[^/]+/pull/([0-9]+)", value)):
        return int(match[1])
    return value


@dataclass(frozen=True)
class Run:
    state: dict = field(default_factory=dict)
    diff_hash: str | None = None
    no_progress: bool = False

    @classmethod
    def from_state(cls, state: dict) -> Run:
        return cls(dict(state), state.get("diff_fingerprint"))


@dataclass(frozen=True)
class Updated:
    ts: float
    fields: dict = field(default_factory=dict)
    outcome: dict = field(default_factory=dict)
    plan_branch: bool = False
    raw: dict | None = field(default=None, kw_only=True, repr=False, compare=False)


@dataclass(frozen=True)
class Planned(Updated):
    pass


@dataclass(frozen=True)
class Synthesized(Updated):
    pass


@dataclass(frozen=True)
class Built(Updated):
    pass


@dataclass(frozen=True)
class Checked(Updated):
    pass


@dataclass(frozen=True)
class Merged(Updated):
    pass


@dataclass(frozen=True)
class Closed(Updated):
    pass


@dataclass(frozen=True)
class Failed(Updated):
    pass


@dataclass(frozen=True)
class Retried(Updated):
    pass


@dataclass(frozen=True)
class FixToBuild(Updated):
    pass


@dataclass(frozen=True)
class Published(Updated):
    pass


@dataclass(frozen=True)
class Fixed(Updated):
    pass


@dataclass(frozen=True)
class RedMain(Updated):
    pass


@dataclass(frozen=True)
class Progress(Updated):
    pass


Event: TypeAlias = Planned | Synthesized | Built | Checked | Merged | Closed | Failed | Retried | FixToBuild | Published | Fixed | RedMain | Progress | Updated


def parse_event(raw: dict) -> Event:
    variants: dict[str, type[Updated]] = {
        "needs_help": Failed, "replan": Planned, "build_complete": Built,
        "retry_succeeded": Retried, "fix_to_build": FixToBuild, "synthesis": Synthesized,
        "published": Published, "verdict": Checked, "fix_complete": Fixed,
        "merge_complete": Merged, "closed": Closed, "red_main": RedMain,
    }
    action = raw.get("action")
    if action is not None and action not in variants:
        raise ValueError(f"unknown transition action: {action}")
    variant = variants[action] if action is not None else Updated
    return variant(raw["ts"], dict(raw["fields"]), dict(raw.get("outcome") or {}),
                   bool(raw.get("plan_branch")), raw=dict(raw))


def event_record(event: Event) -> dict:
    if event.raw is not None:
        return event.raw
    actions = {
        Planned: "replan", Synthesized: "synthesis", Built: "build_complete",
        Checked: "verdict", Merged: "merge_complete",
        Failed: "needs_help", Retried: "retry_succeeded", FixToBuild: "fix_to_build",
        Published: "published", Fixed: "fix_complete", RedMain: "red_main", Closed: "closed",
    }
    raw = {"ts": event.ts, "fields": event.fields}
    if type(event) in actions:
        raw.update(action=actions[type(event)], outcome=event.outcome)
    elif type(event) is not Updated:
        raise ValueError("event is not a persisted transition")
    if event.plan_branch:
        raw["plan_branch"] = True
    return raw


@dataclass(frozen=True)
class RepoSnapshot:
    name: str
    last_attempt: float = 0
    status: dict = field(default_factory=dict)
    prs: tuple[dict, ...] | None = None
    issues: tuple[dict, ...] | None = None
    states: dict[int, dict] = field(default_factory=dict)
    open_prs: frozenset[int] = frozenset()
    busy: bool = False


@dataclass(frozen=True)
class Snapshot:
    repos: tuple[RepoSnapshot, ...]
    now: float
    only_issue: int | None = None


@dataclass(frozen=True)
class Pick:
    repo: str
    issue: int
    kind: Literal["red_main", "prs", "issues", "pr", "issue"]
    target: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    plik: str
    linia_od: int
    linia_do: int
    zmiana: str = ""
    lens: str = ""
    lenses: tuple[str, ...] = ()
    _raw: dict | None = field(default=None, repr=False, compare=False, kw_only=True)


@dataclass(frozen=True)
class Note:
    lens: str
    pytanie: str
    note: str
    _raw: dict | None = field(default=None, repr=False, compare=False, kw_only=True)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Literal["pass", "fail", "unknown"]
    reason: str
    findings: tuple[Finding, ...]


def parse_finding(raw: dict) -> Finding | Note:
    def text(key: str) -> str:
        value = raw.get(key)
        return str(value) if value is not None else ""

    def line(key: str) -> int:
        try:
            return int(raw.get(key) or 0)
        except (TypeError, ValueError, OverflowError):
            return 0

    lens = text("pytanie") or text("lens")
    if text("plik"):
        return Finding(text("plik"), line("linia_od"), line("linia_do"), text("zmiana"), lens,
                       tuple(raw.get("lenses") or ()), _raw=dict(raw))
    return Note(lens, text("pytanie"), text("note"), _raw=dict(raw))


def finding_summary(raw: dict) -> dict:
    item = parse_finding(raw)
    return {"pytanie": item.lens if "pytanie" in raw else raw.get("warstwa", ""),
            "plik": item.plik if isinstance(item, Finding) else "",
            "linie": [item.linia_od if isinstance(item, Finding) and "linia_od" in raw else None,
                      item.linia_do if isinstance(item, Finding) and "linia_do" in raw else None],
            "zmiana": item.zmiana if isinstance(item, Finding) else "",
            "uzasadnienie": (raw.get("uzasadnienie") or raw.get("log") or "")[:300]}


def finding_fingerprint(raw: dict) -> list:
    item = parse_finding(raw)
    return [item.plik if isinstance(item, Finding) else None,
            item.lens if "pytanie" in raw else raw.get("warstwa"),
            item.zmiana if isinstance(item, Finding) and "zmiana" in raw else None]


def finding_key(raw: dict) -> tuple:
    item = parse_finding(raw)
    if not isinstance(item, Finding):
        return ("", "", "", "")
    return (item.plik, item.linia_od if "linia_od" in raw else "",
            item.linia_do if "linia_do" in raw else "", item.zmiana)


def dismissed_key(row: dict) -> list:
    item = parse_finding(row)
    if not isinstance(item, Finding) and not item.pytanie:
        return [row.get("warstwa"), row.get("log")]
    return [item.plik if isinstance(item, Finding) else None,
            item.linia_od if isinstance(item, Finding) and "linia_od" in row else None,
            item.linia_do if isinstance(item, Finding) and "linia_do" in row else None,
            item.lens if "pytanie" in row else None]


def to_dict(item: Finding | Note) -> dict:
    if item._raw is not None:
        raw = dict(item._raw)
    elif isinstance(item, Finding):
        raw = {"plik": item.plik, "linia_od": item.linia_od, "linia_do": item.linia_do,
               "zmiana": item.zmiana, "pytanie": item.lens}
    else:
        raw = {"pytanie": item.pytanie or item.lens, "note": item.note}
    if isinstance(item, Finding):
        if item.lenses:
            raw["lenses"] = list(item.lenses)
        elif raw.get("lenses"):
            raw.pop("lenses")
    return raw
