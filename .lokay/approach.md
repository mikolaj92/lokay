# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/lokay issue=137 -->

Repository: `mikolaj92/lokay`  
Issue: #137 — Tick 60s nie reinstalluje uv i nie puchnie launchd-stdout do GiB

## Goal

Heartbeat 60s na `mini-m4-0` za każdym razem robi `uv run --reinstall-package lokay --reinstall-package fala` i sypie pełny JSON Fala do `launchd-stdout.log`.

## Files likely touched

- `scripts/lokay-mill-daemon.sh`
- `src/lokay/envelope.py`
- `src/lokay/compose/daemon_cycle.py`
- `src/lokay/proc/daemon.py`
- `tests/test_preflight_daemon.py`
- `docs/MILL_HEALTH.md`

## Test plan

- `uv run pytest -q tests/test_preflight_daemon.py tests/test_self_repair_daemon.py tests/test_mill_health.py`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
