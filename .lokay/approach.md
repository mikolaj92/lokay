# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=241 -->

Repository: `mikolaj92/lokay`  
Issue: #241 — organ: pass --issue to pr_create

## Goal

#239 dodało `pr_create --issue` i `reason=issue_closed` gdy issue nie OPEN. Organ woła `pr_create` **bez** `--issue`, więc bramka jest martwa. Zamknięte issue nadal dostaje PR (jak leftover #235 → PR 237).

## Files likely touched

- (infer from repo inspection)

## Test plan

- Test organ/pr_create: argv zawiera `--issue`. Zamknięte issue → create_pr nie wołane.
- Nie ruszaj 180–192, 228, 235.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
