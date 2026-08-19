# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=333 -->

Repository: `mikolaj92/lokay`  
Issue: #333 — factory_begin: cold survey musi pokryć skonfigurowane K

## Goal

`pick_survey_repos` przy pustym last-pass: `lokay` + `extra_cold=2`. `max_issue_to_pr_per_pass` (K) bywa 3–4. Survey widzi za mało czystych repo → tick startuje mniej i2pr niż K.

## Files likely touched

- `src/lokay/proc/factory_begin.py`
- `hot.py`

## Test plan

- K=3, 4 czyste repo z work:ready, pusty last-pass → survey ≥3 repo / i2pr start ≤K ale nie ślepo 2.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
