# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=85 -->

Repository: `mikolaj92/lokay`  
Issue: #85 — Dodać mikolaj92/heimdall do katalogu Lokaya

## Goal

heimdall nie jest w katalogu Lokaya. Kod Heimdala ma iść przez Lokaya, jak reszta. Bez wpisu Lokay nie weźmie ziaren Heimdala.

## Files likely touched

- `repos.mikolaj92.yaml`
- `tests/test_repos_catalog.py`

## Test plan

- Run `uv run pytest -q tests/test_repos_catalog.py`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- No explicit file paths in issue; infer from repo inspection.
