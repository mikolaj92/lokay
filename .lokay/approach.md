# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=269 -->

Repository: `mikolaj92/lokay`  
Issue: #269 — park_closed_ready: zdejmij leftover work:ready z CLOSED

## Goal

`closeout_pr` (#267 / PR 268) zdejmuje `work:ready`/`ai:ready` tylko w tym samym przebiegu, w którym merdżuje PR. Merge, który wnosi park, jedzie jeszcze starym kodem. Kolejny przebieg nie widzi już zmergowanego PR — etykiety zostają na CLOSED.

## Files likely touched

- (infer from repo inspection)

## Test plan

- CLOSED + `work:ready` → park/remove-label.
- OPEN + `work:ready` → nie ruszać.
- Brak CLOSED leftover → no-op, `ok`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
