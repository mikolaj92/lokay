# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=275 -->

Repository: `mikolaj92/lokay`  
Issue: #275 — pr_merge: zdejmij work:ready po udanym merge

## Goal

`closeout_pr` (#267) parkuje etykiety tylko gdy sam merdżuje w tym przebiegu. Merge przez `pr_merge` / `gh pr merge` (Fixes #N) zamyka issue, ale `work:ready`/`ai:ready` zostają — closeout kolejnego przebiegu nie widzi już otwartego PR.

## Files likely touched

- `pr_merge.py`
- `src/lokay/proc/pr_merge.py`

## Test plan

- Merge + znany issue → park/remove-label.
- Merge bez issue / dry-run → etykiet nie ruszać.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
