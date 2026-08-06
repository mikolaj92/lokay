# WORKING machine (Definition of Done)

Lokay is **working** only if it continuously mills **all** work across
configured repos. Order lives in Fala; atoms are Unix small programs.

## Full pass (one tick)

1. **Survey** every configured repo (read-only network): inbox, `ai:ready`, open `ai/fix/*` PRs.
2. **Inbox triage** (before ready): undecided open issues → `ai:ready` | `ai:needs-feedback` | OOS close. Path: `issue_triage`.
3. **Implement ready**: Fala `issue_to_pr` → agent → commit/push → PR. Skip ready issues that already have an open `ai/fix/*` PR (owned by PR triage). Stuck failures → ledger → `ai:blocked`. Live ready work with `executor.enabled: false` is a **stall** (agent never runs).
4. **PR triage**: checks status `passed|failed|pending|none`; `mergeable=CONFLICTING|DIRTY` → close PR + re-label linked issue `ai:ready` (re-implement next pass); failed → `pr_repair`; mergeable + `merge.enabled` → `pr_triage` (checks → merge → close linked issue).
5. **Health**
   - `idle` — survey found no inbox, ready, or open AI PRs
   - `progress` — this pass advanced work
   - `waiting` — open PRs but not actionable under current policy
   - `work_remaining` — survey saw work without mutations (not a green noop)
   - `stall` — live actionable work but zero progress (**ok=false**)

Mutations require `mode: live`, `--live`, and for the agent slot `executor.enabled`.

Composers (`issue_to_pr`, `pr_repair`, `pr_triage`) run as **Unix atom pipelines** by
default. Set `LOKAY_USE_FALA=1` to force the Fala host (currently can abort on
package load in some environments).

## Status (is the machine WORKING?)

```bash
uv run lokay status --config config.yaml
# or: uv run lokay-status --config config.yaml
```

Reports `mill_ready`, `blockers` (mode/executor/merge/require_checks/clones),
and survey `remaining`. **ok=false** when work remains but mill is not live-ready
(NOT WORKING). Live ticks also remove `ai:ready` once an open AI PR owns the issue.

## Continuous mill

```bash
# need: mode: live, executor.enabled, merge.enabled;
# for no-CI repos: merge.require_checks: false
uv run lokay-mill --config config.yaml --live --max-passes 8
```

Or keep a safe dry-run `config.yaml` and enable live via env (no file rewrite):

```bash
export LOKAY_MODE=live
export LOKAY_EXECUTOR_ENABLED=1
export LOKAY_AGENT=fake          # or grok
export LOKAY_MERGE_ENABLED=1
export LOKAY_REQUIRE_CHECKS=0    # canary / no-CI
uv run lokay-mill --config config.yaml --live --max-passes 8
```

Runs bounded tick passes until `idle`, stall, wait, or budget. External
schedulers re-invoke; the process does not sleep forever.

## Idle rule

May no-op **only** after a full multi-repo survey with **no** remaining
actionable work. Green/planned ticks while work remains are **NOT WORKING**.

## Graphs

See [`GRAPH.md`](GRAPH.md): `issue_to_pr`, `issue_triage`, `pr_repair`, `pr_triage`.
