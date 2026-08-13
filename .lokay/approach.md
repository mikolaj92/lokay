# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=91 -->

Repository: `mikolaj92/lokay`  
Issue: #91 — Równe taski równolegle: 2–4, jeden na repo, nie jeden globalnie

## Goal

Lokaj jedzie serialnie: jeden `pi` globalnie. Jedna sprawa w jednym repo (np. cały korpus Sejmu) zjada kolejkę wszystkich innych. Mini M4 uniesie 2–4 równe taski naraz — **w różnych repo**.

## Files likely touched

- (infer from repo inspection)

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- No explicit file paths in issue; infer from repo inspection.
