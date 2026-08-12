# Autonomy (Definition of Working)

Lokay is **working as an autonomous mill** when it continuously turns human-authored
issues into merged results across the managed catalog — without new human gates,
without freezing clean repos behind a busy peer, and without treating honest waits
as recovery stalls.

Design law: **Fala coordinates; small atoms do one job.** Certainty scaffolding
here is additive (tests / fixtures / docs / config profile). Tick scheduling may
move into Fala later; the promises below are the public surface that must remain.

## Product promises (mill pass)

1. **Per-repo PR-first** — An actionable `ai/fix/*` PR in repo A does **not**
   block inbox triage or `issue_to_pr` in clean repo B. Never open a second AI PR
   in a repo that already has one.
2. **Parallel K** — Up to `limits.max_issue_to_pr_per_pass` (default **3**)
   `issue_to_pr` runs per factory pass across **different** clean repos.
3. **Intake gates implement** — Deterministic intake yields `CLOSE` | `SPLIT` |
   `READY` (rare `NEEDS_HUMAN`). Only `READY` + `--require-ready` may call
   `issue_to_pr`. CLOSE/SPLIT never implement.
4. **Trusted merge policy** — With merge armed: pending checks → `waiting`;
   red checks → `repair`; approve + green → merge; secrets / needs_human /
   escalated `ai:needs-review` → fail closed.
5. **Narrow recovery** — Mill `health=waiting` / `repairing` (and soft
   merge_policy reasons) never mint recovery stall fingerprints or fill the
   4-of-5 self-repair quorum.

Humans **author issues**. The mill consumes them. Residual mailbox
(`lokay status --human`) is exception reporting, not a workflow step.

## Night mill profile

Default example stays dry-run (`config.example.yaml`). For a live night mill,
use the documented profile:

```bash
cp config.live-autonomous.example.yaml config.yaml
# Or point LaunchAgent at the live profile path.
uv run lokay validate --config config.yaml
uv run lokay status --config config.yaml --local
uv run lokay-mill --config config.yaml --live --max-passes 8
```

Profile knobs (also overridable via env):

| Knob | Live autonomous |
| --- | --- |
| `mode` | `live` (`LOKAY_MODE=live`) |
| `executor.enabled` | `true` (`LOKAY_EXECUTOR_ENABLED=1`) |
| `merge.enabled` | `true` (`LOKAY_MERGE_ENABLED=1`) |
| `merge.require_checks` | `true` (`LOKAY_REQUIRE_CHECKS=1`) |
| `merge.require_llm_review` | `true` (`LOKAY_REQUIRE_LLM_REVIEW=1`) |
| `limits.max_issue_to_pr_per_pass` | `3` |

## Hermetic canaries

Contract tests pin the promises without live network / gh mutation:

```bash
uv run pytest -q tests/test_autonomy_contracts.py
```

Broader related suites: `tests/test_global_pr_first.py`,
`tests/test_intake*.py`, `tests/test_merge_policy.py`,
`tests/test_recovery_history.py`. Fixtures live under `tests/fixtures/autonomy.py`.

Do **not** add live canaries that mutate real repos. Do **not** ship
canary-only “fixes” (`LOKAY_CANARY.md` style) — see [`NO_STUBS.md`](NO_STUBS.md).

## Reading `lokay status` and `last-pass.json`

```bash
uv run lokay status --config config.yaml
uv run lokay status --config config.yaml --local   # readiness + last_pass
uv run lokay status --config config.yaml --human   # residual mailbox only
```

Each tick writes a compact receipt (default `~/.lokay/last-pass.json`):

```bash
jq '{health, idle, progress, merge_enabled, require_checks, require_llm_review, k: .max_issue_to_pr_per_pass, remaining, by_repo}' \
  ~/.lokay/last-pass.json
```

| `health` | Meaning for autonomy |
| --- | --- |
| `idle` | No remaining actionable work |
| `progress` | Queue moved this pass |
| `waiting` | Pending CI / review limbo — honest wait, not stall |
| `repairing` | Repair / request_changes cycle — honest wait |
| `stall` | Actionable work with no progress — investigate |
| `survey_error` | List atoms failed — fix auth/network before trusting idle |

`ok=false` means **not working** (work remains but mill not live-ready, or
survey errors). Soft waits with `ok=true` are healthy autonomy.

Details: [`WORKING.md`](WORKING.md), [`MILL_HEALTH.md`](MILL_HEALTH.md),
[`GRAPH.md`](GRAPH.md).
