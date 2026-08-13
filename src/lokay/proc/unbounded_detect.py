"""Atomic: classify issue title+body as unbounded (no ceiling).

Stdin JSON ``{title, body}`` → stdout JSON ``{unbounded, reason}``.
Unbounded = no upper bound (full corpus, fill history, months,
``zbierz wszystko``). Fail-closed: no finite done-condition → unbounded=true.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

from lokay.envelope import emit_exit, err, ok, read_stdin_json

# --- unbounded signals (no ceiling) ---

_FULL_CORPUS = re.compile(
    r"(?i)(?:"
    r"\b(?:full|entire|whole|complete)\s+corpus\b"
    r"|\b(?:cał[yeia]|pełn\w*)\s+korpus\b"
    r"|\bkorpus\s+sejmu\b"
    r"|\bsejm\s+corpus\b"
    r")"
)
_FILL_HISTORY = re.compile(
    r"(?i)(?:"
    r"\b(?:fill|populate|backfill)\s+(?:the\s+)?(?:entire\s+|full\s+|whole\s+)?"
    r"history\b"
    r"|\bnape[łl]ni\w*\s+histori"
    r"|\bzape[łl]ni\w*\s+histori"
    r")"
)
_COLLECT_EVERYTHING = re.compile(
    r"(?i)(?:"
    r"\bzbierz\s+wszystk\w*\b"
    r"|\b(?:collect|gather|scrape|harvest|crawl|ingest)\s+"
    r"(?:everything|all(?:\s+(?:of\s+)?(?:it|them|data|records|docs|documents))?)\b"
    r"|\b(?:inventory|audit|enumerate|catalog)\s+(?:everything|all)\b"
    r")"
)
_NO_UPPER_BOUND = re.compile(
    r"(?i)(?:"
    r"\bunbounded\b"
    r"|\bbez\s+stropu\b"
    r"|\b(?:no|without|brak)\s+(?:an?\s+)?(?:upper\s+)?(?:bound|limit|cap|stropu|limitu|ograniczenia)\b"
    r")"
)
_OPEN_MONTHS = re.compile(
    r"(?i)(?:"
    r"\b(?:for|over|across|during)\s+months\b"
    r"|\bmonths\s+of\b"
    r"|\b(?:takes?|taking|lasts?|lasting)\s+months\b"
    r"|\b(?:several|many|miesi[ąa]cami)\s+months\b"
    r"|\bprzez\s+miesi[ąa]c"
    r"|\bmiesi[ąa]cami\b"
    r")"
)

# Collection-shaped work that still needs a finite cap (fail-closed).
_COLLECTION_SHAPE = re.compile(
    r"(?i)(?:"
    r"\b(?:collect|gather|scrape|harvest|crawl|ingest|backfill|populate|archive)\b"
    r"|\b(?:zbierz|zbieraj|zbiór)\b"
    r"|\b(?:korpus|corpus)\b"
    r"|\bnape[łl]ni"
    r")"
)

# --- finite done-conditions (upper bound present) ---

_DONE_WHEN = re.compile(
    r"(?i)(?:"
    r"\bdone\s+(?:means|when|iff?)\b"
    r"|\bdefinition\s+of\s+done\b"
    r"|\bacceptance(?:\s+criteria)?\b"
    r"|\bskończone\s+gdy\b"
    r"|\bgotowe\s+gdy\b"
    r")"
)
_NUMERIC_CAP = re.compile(
    r"(?i)(?:"
    r"\b(?:at\s+most|no\s+more\s+than|up\s+to|first|max(?:imum)?|"
    r"limit(?:ed)?(?:\s+to)?|cap(?:ped)?(?:\s+at)?|bounded(?:\s+to)?)\s+\d+"
    r"|\b\d+\s+(?:items?|records?|files?|docs?|documents?|rows?|"
    r"sittings?|pages?|issues?|prs?)\b"
    r")"
)
_LOOKBACK_WINDOW = re.compile(
    r"(?i)\b(?:last|past|previous|ostatni\w*|poprzedni\w*)\s+"
    r"(?:\d+\s+)?(?:days?|weeks?|months?|years?|dzie[nń]|dni|tygodn\w*|miesi[ęąa]c\w*)"
)
_END_DATE = re.compile(r"(?i)\buntil\s+\d{4}-\d{2}-\d{2}\b")
_CHECKBOX = re.compile(r"(?m)^\s*[-*]\s*\[[ xX]\]\s+\S")
_PATH = re.compile(
    r"(?:`[^`]+`|(?:src|tests|docs|fala|scripts)/[\w./\-]+)"
)
_FINITE_VERB = re.compile(
    r"(?i)\b(?:fix|add|implement|patch|create|remove|delete|update|"
    r"refactor|wire|restore|rename|move)\b"
)
_UNIVERSAL = re.compile(
    r"(?i)\b(?:everything|all\s+of\s+(?:it|them|history)|wszystk\w*|cał[yeia])\b"
)


def detect(title: str = "", body: str = "") -> dict[str, Any]:
    """Return ``{unbounded, reason}``. Fail-closed when no finite done-condition."""
    blob = f"{title or ''}\n{body or ''}".strip()
    if not blob:
        return {"unbounded": True, "reason": "empty_spec"}

    bound = _finite_bound_reason(blob)
    signal = _unbounded_signal_reason(blob)
    if bound:
        return {"unbounded": False, "reason": bound}
    if signal:
        return {"unbounded": True, "reason": signal}
    if _COLLECTION_SHAPE.search(blob) and not bound:
        return {"unbounded": True, "reason": "no_finite_done_condition"}
    if _looks_finite_change(blob):
        return {"unbounded": False, "reason": "finite_change"}
    return {"unbounded": True, "reason": "no_finite_done_condition"}


def _unbounded_signal_reason(blob: str) -> str | None:
    if _FULL_CORPUS.search(blob):
        return "full_corpus"
    if _FILL_HISTORY.search(blob):
        return "fill_history"
    if _COLLECT_EVERYTHING.search(blob):
        return "collect_everything"
    if _NO_UPPER_BOUND.search(blob):
        return "no_upper_bound"
    if _OPEN_MONTHS.search(blob):
        return "open_duration"
    return None


def _finite_bound_reason(blob: str) -> str | None:
    if _DONE_WHEN.search(blob):
        return "finite_done_condition"
    if _NUMERIC_CAP.search(blob):
        return "numeric_cap"
    if _LOOKBACK_WINDOW.search(blob):
        return "lookback_window"
    if _END_DATE.search(blob):
        return "end_date"
    if _CHECKBOX.search(blob):
        return "checkbox_done_condition"
    return None


def _looks_finite_change(blob: str) -> bool:
    if _PATH.search(blob):
        return True
    if _FINITE_VERB.search(blob) and not _UNIVERSAL.search(blob):
        return True
    return False


def run_detect(payload: Any) -> dict[str, Any]:
    """Classify a stdin JSON object. Envelope on parse failure."""
    if not isinstance(payload, dict):
        return err("stdin must be JSON object with title, body")
    result = detect(str(payload.get("title") or ""), str(payload.get("body") or ""))
    return ok(**result)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="lokay-unbounded-detect").parse_args(argv)
    try:
        payload = read_stdin_json()
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(f"stdin JSON: {exc}"))
    if payload is None:
        return emit_exit(ok(**detect("", "")))
    return emit_exit(run_detect(payload))


if __name__ == "__main__":
    raise SystemExit(main())
