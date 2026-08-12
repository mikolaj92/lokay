# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=66 -->

Repository: `mikolaj92/lokay`  
Issue: #66 — Preflight failure 6bbe372b6ef4befe

## Goal

<!-- lokay-preflight:6bbe372b6ef4befe -->
Bounded checks failed: github_git_transport

## Files likely touched

- `src/lokay/preflight.py`
- `tests/test_git_transport_preflight.py`

## Test plan

- Exercise transport validation, including transient failure retry and bounded persistent failure

## Non-goals

- Weakening canonical SSH-origin validation or allowing interactive authentication
- Increasing the existing 20-second transport-check budget

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- No explicit file paths in issue; infer from repo inspection.
