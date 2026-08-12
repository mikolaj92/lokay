# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=serial-step-3 -->

Repository: `mikolaj92/lokay`  
Issue: serial step 3 — plan atom before run_agent

## Goal

Before the coding `run_agent` in `issue_to_pr`, write a short deterministic approach plan onto the branch (`.lokay/approach.md`) so later `pr_review` can compare the diff to the plan as soft evidence. Trust-with-evidence for intentional issues — not a human approval gate and not NEEDS_HUMAN by default.

## Files likely touched

- `src/lokay/approach_plan.py`
- `src/lokay/proc/plan_issue.py`
- `src/lokay/fala_organ.py`
- `src/lokay/graph_run.py`
- `fala/lokay.fala-package.toml`
- `src/lokay/data/lokay.fala-package.toml`
- `src/lokay/pr_review.py`
- `src/lokay/proc/pr_review.py`
- `src/lokay/prompts.py`
- `tests/test_plan_issue.py`
- `tests/test_graph.py`
- `docs/GRAPH.md`
- `docs/AUTONOMY.md`
- `docs/WORKING.md`
- `docs/UNIX.md`

## Test plan

- Hermetic atom tests for deterministic extraction + live write
- Graph order: `plan_issue` before `run_agent` in `issue_to_pr`
- Soft approach signal in `review_prompt` (missing = nit only)
- Full `uv run pytest -q` green

## Non-goals

- Merge-disabled → waiting health fix (serial step 4)
- Live smoke
- Parallel agents
- Wiring `plan_issue` into `pr_repair` (optional; deferred)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
