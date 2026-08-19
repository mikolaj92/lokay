# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=188 -->

Repository: `mikolaj92/lokay`  
Issue: #188 — Issue z listą Files: localize bez czekania na pi

## Goal

#180, #184, #187: `localize` adapter_timeout → `run_agent` localize_empty → plan_only w ~3 min. Nawet gdy issue ma sekcję Files (187: pr_create.py, git_real_diff.py, pi_budget.py) pi localize i tak timeoutuje. #183 przeszło dopiero gdy ścieżki były w body **i** pi zdążył.

## Files likely touched

- `lokay/localize.json`
- `src/lokay/localize.py`
- `src/lokay/localize_agent.py`
- `tests/test_localize.py`

## Test plan

- Issue body z `## Files` + `src/lokay/localize.py` → localize.json ma tę ścieżkę bez agenta. Puste Files → jak dziś (albo fail-closed, nie wisieć 3 min).

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
