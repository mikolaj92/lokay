# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=897 -->

Repository: `mikolaj92/lokay`  
Issue: #897 — Dział: pr_repair (poprawka PR)

## Goal

Dział: poprawka istniejącego PR. Tylko po werdykcie sita PR albo czerwonym teście. Nie pierwsze pisaninie.

## Files likely touched

- `fala/lokay.fala-package.toml`
- `src/lokay/proc/select_pr_repair.py`
- `src/lokay/proc/run_parent_pr_repair_subflow.py`
- `src/lokay/organ/prs_boundary.py`
- `src/lokay/organ/pr_outcome.py`
- `README.md`, `docs/GRAPH.md`

## Test plan

- `uv run pytest -q tests/test_select_pr_repair.py tests/test_prs_fala.py tests/test_pr_outcome_fala.py tests/test_triage.py tests/test_graph.py tests/test_readme_state_machine.py`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
