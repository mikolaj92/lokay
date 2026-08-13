# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=88 -->

Repository: `mikolaj92/lokay`  
Issue: #88 — Atom localize przed run_agent (Agentless: plik zanim patch)

## Goal

Przed `run_agent` Fala woła mały atom `localize`: lista plików/katalogów do edycji (drzewo repo + treść ziarna). Agent pisze patch tylko tam. LLM nie wybiera kroku linii.

## Files likely touched

- `src/lokay/localize.py`
- `src/lokay/proc/localize.py`
- `src/lokay/fala_organ.py`
- `src/lokay/prompts.py`
- `src/lokay/graph_run.py`
- `src/lokay/git_commit.py`
- `fala/lokay.fala-package.toml`
- `src/lokay/data/lokay.fala-package.toml`
- `pyproject.toml`
- `docs/GRAPH.md`
- `docs/UNIX.md`
- `tests/test_localize.py`
- `tests/test_graph.py`
- `tests/test_triage.py`
- `tests/test_plan_issue.py`

## Test plan

- `uv run pytest -q tests/test_localize.py tests/test_graph.py tests/test_plan_issue.py tests/test_triage.py tests/test_fala_package_lock.py`

## Non-goals

- Embedding service / second planner LLM
- Parallel agents or concurrent worktrees
- Changing self_repair path (separate emergency lane)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Order: `plan_issue → localize → run_agent`; empty localize fails closed.
