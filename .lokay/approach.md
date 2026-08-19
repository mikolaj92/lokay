# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=195 -->

Repository: `mikolaj92/lokay`  
Issue: #195 — detach: pierwsza linia w logu i2pr przy starcie

## Goal

#193 miał log 0 bajtów przez cały lot. Olej nie widzi czy i2pr żyje.

## Files likely touched

- `src/lokay/proc/detach_issue_to_pr.py`
- `tests/test_dispatch_detach.py`

## Test plan

- Po `detach_issue_to_pr` (mock spawn) plik logu nie jest pusty i zawiera `started`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
