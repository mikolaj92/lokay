"""Fala bindings for explicit repository-local pass-plan fragments."""

from typing import Any

SLOT_COUNT = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_pass_plan(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "prepare_pass_plan":
        from lokay.proc.prepare_pass_plan import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_plan_repo_"):
        from lokay.proc.select_plan_repo_slot import select

        return select(up.get("prepare_pass_plan") or {}, slot=slot)
    if atom.startswith("build_repo_plan_fragment_"):
        from lokay.proc.build_repo_plan_fragment import build

        return build(
            pass_dir=pass_dir,
            prepared=up.get("prepare_pass_plan") or {},
            selected=up.get(f"select_plan_repo_{slot}") or {},
        )
    if atom.startswith("record_repo_plan_fragment_"):
        from lokay.proc.record_repo_plan_fragment import record

        return record(
            up.get(f"select_plan_repo_{slot}") or {},
            up.get(f"build_repo_plan_fragment_{slot}") or {},
        )
    if atom == "reduce_pass_plan":
        from lokay.passkit import io as pass_io
        from lokay.proc.reduce_pass_plan import reduce_state

        working = pass_io.read_json(pass_io.working_path(pass_dir))
        fragments = [
            up.get(f"record_repo_plan_fragment_{i}") or {}
            for i in range(1, SLOT_COUNT + 1)
        ]
        return reduce_state(
            prepared=up.get("prepare_pass_plan") or {},
            fragments=fragments,
            working=working,
        )
    if atom == "persist_pass_plan":
        from lokay.proc.persist_pass_plan import persist

        return persist(pass_dir=pass_dir, reduced=up.get("reduce_pass_plan") or {})
    if atom == "summarize_pass_plan":
        from lokay.proc.summarize_pass_plan import summarize

        return summarize(up.get("persist_pass_plan") or {})
    return None
