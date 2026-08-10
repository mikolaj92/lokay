# WORKING machine (Definition of Done)

Lokay is **working** only if it continuously mills **all** work across
configured repos (`repos.mikolaj92.yaml`). Order: triage → **PR close-out** → implement (serial).
Agent must be **real** ([`NO_STUBS.md`](NO_STUBS.md)).

## Full pass (one tick)

1. **Survey** every managed repo: inbox, `ai:ready`, open `ai/fix/*` PRs.
2. **Inbox triage** (before ready): undecided issues → `ai:ready` | `ai:needs-feedback` | OOS. Path: `issue_triage`.
3. **PR-first close-out**: for open AI PRs — conflicts → close + re-ready; failed → `pr_repair`; mergeable + policy → merge → close issue. Land code before opening new fronts.
4. **Implement ready (serial)**: at most one `issue_to_pr` per tick, **only** in a repo with **zero** open AI PRs. configured executor → commit/push → PR. Worktree from `origin/main`. Stuck → ledger → `ai:blocked`. Live ready with `executor.enabled: false` is a **stall**.
5. **Health**: `idle` only when survey finds no actionable work. Survey work without mutations → **not** a green success.

## Continuous mill

LaunchAgent or:

```bash
export LOKAY_MODE=live
export LOKAY_EXECUTOR_ENABLED=1
export LOKAY_AGENT=omp   # log label only; binary is executor.command in config
export LOKAY_MERGE_ENABLED=1
# LOKAY_REQUIRE_CHECKS=1 default (set 0 only if you accept merge without CI)
uv run lokay-mill --config config.yaml --live --max-passes 8
```

```bash
uv run lokay status --config config.yaml
```

**ok=false** when work remains but mill is not live-ready → NOT WORKING.

## Idle rule

May no-op **only** after a full multi-repo survey with **no** remaining actionable work.

## Graphs

See [`GRAPH.md`](GRAPH.md).

- `pr_review`: structured LLM gate before auto-merge when `merge.require_llm_review`.
