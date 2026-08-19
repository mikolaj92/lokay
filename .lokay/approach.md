# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=319 -->

Repository: `mikolaj92/lokay`  
Issue: #319 — pick_survey_repos: pusty katalog nie wolno pełnych 29 repo

## Goal

Pusty katalog. `last-pass` ma `health=pass_ceiling` i `remaining=None`. `pick_survey_repos` przy pustym `prev_by_repo` (i przy zerowym hot) zwraca **całe 29 repo**. Jeden przebieg: 29× list_prs + list_inbox + list_issues. To zjada strop 180s zanim mill zdąży oddać idle.

## Files likely touched

- `src/lokay/passkit/hot.py`

## Test plan

- 29 nazw, `prev_by_repo={}` albo same zera → wynik ma lokay i `len <= 1+extra_cold`, nie 29.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
