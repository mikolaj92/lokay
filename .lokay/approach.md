# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=93 -->

Repository: `mikolaj92/lokay`  
Issue: #93 — Zbiór bez stropu: zbieracz w tle, nie pi

## Goal

After the separate unbounded-collection detection gate, a seed is handled as a
bounded collector/bootstrap patch whose deployment starts durable background
collection after merge. Pi and the mill must neither populate collection data
nor wait for collection completion; a later seed evaluates accrual.

## Files likely touched

- `src/lokay/agent.py`
- `src/lokay/approach_plan.py`
- `src/lokay/pr_review.py`
- `tests/test_intake_mill_gate.py`
- `tests/test_plan_issue.py`
- `tests/test_pr_review.py`
- `docs/AUTONOMY.md`
- `docs/WORKING.md`
- `docs/GRAPH.md`
- `docs/NO_STUBS.md`
- `docs/MILL_SMOKE.md`
- `scripts/lokay-mill-daemon.sh`

## Test plan

- Run targeted agent, approach-plan, PR-review, and mill-gate tests
- Run the full hermetic pytest suite

## Non-goals

- Implement or change the separate unbounded-collection detection gate
- Have Pi or the mill populate collection data, poll it, or await completion
- Add a parallel collection operator to the mill

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- The collector boundary is enforced at the coding and PR-review prompt boundaries; collector deployment remains the bounded patch's responsibility.
- No explicit file paths in issue; infer from repo inspection.
