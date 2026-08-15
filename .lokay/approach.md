# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=136 -->

Repository: `mikolaj92/lokay`  
Issue: #136 — test_local nie pali native/Fala pytestem z urzędu

## Goal

Fala #164 pali cały slot `issue_to_pr` (~20 min) na `uv run --extra dev pytest -q`: 51 faili native/Mojo, potem jedna naprawa, potem `pr_create` odmawia (`test_local_recheck_failed`). README issue nigdy nie dochodzi do PR.

## Files likely touched

- `src/lokay/proc/test_local.py` — run only a repo-declared command
- `pyproject.toml` — `[tool.lokay] test` for this checkout
- `README.md` — document repository-declared verification
- `tests/test_test_local.py` — skip without declaration; run declared argv

## Test plan

- `uv run pytest -q tests/test_test_local.py tests/test_fala_organ.py`

## Non-goals

- Do not rewrite Fala or invent a native/Mojo verifier here
- Do not map worktree → `repos.mikolaj92.yaml` (declaration lives in the checkout)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
