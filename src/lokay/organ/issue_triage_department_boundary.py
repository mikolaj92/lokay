"""Fala bindings for the issue_triage department (sieve + split + intake)."""

from typing import Any


def _listed_of(inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    listed = up.get("list_open_issues") or inputs.get("listed") or {}
    return listed if isinstance(listed, dict) else {}


def _last_of(inputs: dict[str, Any]) -> dict[str, Any]:
    last = inputs.get("last") or {}
    return last if isinstance(last, dict) else {}


def _slot(atom: str) -> int:
    suffix = atom.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def handle_issue_triage_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "prepare_issue_sieve":
        from lokay.execution_contracts import ISSUE_SIEVE_SLOT_COUNT
        from lokay.proc.prepare_issue_sieve import prepare

        budget = inputs.get("budget")
        return prepare(
            listed=_listed_of(inputs, up),
            last=_last_of(inputs),
            pass_dir=pass_dir,
            config_path=config,
            live=live,
            budget=int(budget) if budget is not None else None,
            slot_count=ISSUE_SIEVE_SLOT_COUNT,
        )
    slot = _slot(atom)
    if atom.startswith("select_issue_sieve_slot_"):
        from lokay.proc.select_issue_sieve_slot import select

        return select(
            up.get("prepare_issue_sieve") or {},
            up.get(f"classify_issue_sieve_row_{slot-1}") or {},
            slot=slot,
        )
    if atom.startswith("run_issue_sieve_row_"):
        from lokay.proc.run_issue_sieve_row import run

        prepared = up.get("prepare_issue_sieve") or {}
        previous = up.get(f"classify_issue_sieve_row_{slot-1}") or {}
        last = previous.get("result") if previous.get("result") else prepared.get("last")
        return run(
            listed=prepared.get("listed") or _listed_of(inputs, up),
            last=last if isinstance(last, dict) else {},
            pass_dir=str(prepared.get("pass_dir") or pass_dir),
            config_path=str(prepared.get("config_path") or config or "") or None,
            live=bool(prepared.get("live") if "live" in prepared else live),
            slot=slot,
        )
    if atom.startswith("classify_issue_sieve_row_"):
        from lokay.proc.classify_issue_sieve_row import classify

        return classify(
            up.get(f"select_issue_sieve_slot_{slot}") or {},
            up.get(f"run_issue_sieve_row_{slot}") or {},
            prepared=up.get("prepare_issue_sieve") or {},
        )
    if atom == "select_issue_sieve_result":
        from lokay.execution_contracts import ISSUE_SIEVE_SLOT_COUNT
        from lokay.proc.select_issue_sieve_result import select

        return select(
            up.get("prepare_issue_sieve") or {},
            [
                up.get(f"classify_issue_sieve_row_{i}") or {}
                for i in range(1, ISSUE_SIEVE_SLOT_COUNT + 1)
            ],
        )
    if atom == "run_issue_sieve_rows":
        from lokay.proc.run_issue_sieve_rows import run

        return run(
            listed=_listed_of(inputs, up),
            config_path=config,
            live=live,
            pass_dir=pass_dir,
            last=_last_of(inputs),
        )
    if atom == "select_issue_sieve":
        from lokay.proc.select_issue_sieve import select

        return select(
            up.get("select_next_issue") or {},
            up.get("issues_run_triage") or {},
            _listed_of(inputs, up),
        )
    if atom == "run_issue_sieve_split":
        from lokay.proc.run_issue_sieve_split import run

        return run(up.get("select_issue_sieve") or {}, config_path=config, live=live)
    if atom == "run_issue_sieve_intake":
        from lokay.proc.run_issue_sieve_intake import run

        return run(up.get("select_issue_sieve") or {}, config_path=config, live=live)
    if atom == "summarize_issue_sieve_row":
        from lokay.proc.summarize_issue_sieve_row import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_sieve") or {},
            up.get("run_issue_sieve_split") or {},
            up.get("run_issue_sieve_intake") or {},
        )
    if atom == "summarize_issue_triage_department":
        from lokay.proc.summarize_issue_triage_department import summarize

        return summarize(up.get("run_issue_sieve_rows") or {})
    return None
