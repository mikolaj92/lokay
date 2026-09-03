"""Fala bindings for the executor department (code and PR, not sieve)."""

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


def handle_executor_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "prepare_executor_rows":
        from lokay.execution_contracts import EXECUTOR_SLOT_COUNT
        from lokay.proc.prepare_executor_rows import prepare

        budget = inputs.get("budget")
        if budget is None:
            budget = inputs.get("issue_budget")
        return prepare(
            listed=_listed_of(inputs, up),
            last=_last_of(inputs),
            pass_dir=pass_dir,
            config_path=config,
            live=live,
            budget=int(budget) if budget is not None else None,
            slot_count=EXECUTOR_SLOT_COUNT,
        )
    slot = _slot(atom)
    if atom.startswith("select_executor_slot_"):
        from lokay.proc.select_executor_slot import select

        return select(
            up.get("prepare_executor_rows") or {},
            up.get(f"classify_executor_row_{slot-1}") or {},
            slot=slot,
        )
    if atom.startswith("run_executor_row_"):
        from lokay.proc.run_executor_row import run

        prepared = up.get("prepare_executor_rows") or {}
        previous = up.get(f"classify_executor_row_{slot-1}") or {}
        last = previous.get("result") if previous.get("result") else prepared.get("last")
        return run(
            listed=prepared.get("listed") or _listed_of(inputs, up),
            last=last if isinstance(last, dict) else {},
            pass_dir=str(prepared.get("pass_dir") or pass_dir),
            config_path=str(prepared.get("config_path") or config or "") or None,
            live=bool(prepared.get("live") if "live" in prepared else live),
            slot=slot,
        )
    if atom.startswith("classify_executor_row_"):
        from lokay.proc.classify_executor_row import classify

        prepared = dict(up.get("prepare_executor_rows") or {})
        previous = up.get(f"classify_executor_row_{slot-1}") or {}
        if previous.get("spent") is not None:
            prepared["spent"] = previous["spent"]
        return classify(
            up.get(f"select_executor_slot_{slot}") or {},
            up.get(f"run_executor_row_{slot}") or {},
            prepared=prepared,
        )
    if atom == "select_executor_result":
        from lokay.execution_contracts import EXECUTOR_SLOT_COUNT
        from lokay.proc.select_executor_result import select

        return select(
            up.get("prepare_executor_rows") or {},
            [
                up.get(f"classify_executor_row_{i}") or {}
                for i in range(1, EXECUTOR_SLOT_COUNT + 1)
            ],
        )
    if atom == "select_issue_do_row":
        from lokay.proc.select_issue_do_row import pick, select

        picked = up.get("select_next_issue") or pick(
            _listed_of(inputs, up), _last_of(inputs)
        )
        return select(picked, _listed_of(inputs, up))
    if atom == "run_executor_rows":
        from lokay.proc.run_executor_rows import run

        budget = inputs.get("issue_budget")
        return run(
            listed=_listed_of(inputs, up),
            config_path=config,
            live=live,
            pass_dir=pass_dir,
            budget=int(budget) if budget is not None else None,
            last=_last_of(inputs),
        )
    if atom == "summarize_executor_row":
        from lokay.proc.summarize_executor_row import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_executor") or up.get("select_issue_do_row") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=pass_dir,
        )
    if atom == "summarize_executor_department":
        from lokay.proc.summarize_executor_department import summarize

        return summarize(up.get("run_executor_rows") or {})
    return None
