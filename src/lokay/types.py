from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Finding:
    plik: str
    linia_od: int
    linia_do: int
    zmiana: str
    lens: str
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
        return Finding(text("plik"), line("linia_od"), line("linia_do"), text("zmiana"), lens, _raw=dict(raw))
    return Note(lens, text("pytanie"), text("note"), _raw=dict(raw))


def to_dict(item: Finding | Note) -> dict:
    if item._raw is not None:
        return dict(item._raw)
    if isinstance(item, Finding):
        return {"plik": item.plik, "linia_od": item.linia_od, "linia_do": item.linia_do,
                "zmiana": item.zmiana, "pytanie": item.lens}
    return {"pytanie": item.pytanie or item.lens, "note": item.note}
