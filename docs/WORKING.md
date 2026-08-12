# WORKING machine (Definition of Done)

Lokay is **working** only if it continuously mills **all** work across
configured repos (`repos.mikolaj92.yaml`). Order: survey → **global PR-first**
(close-out) → inbox triage / implement (only when no actionable AI PRs remain).
Agent must be **real** ([`NO_STUBS.md`](NO_STUBS.md)).

## Full pass (one tick)

1. **Survey** every managed repo: inbox, `ai:ready`, open `ai/fix/*` PRs.
2. **Global PR-first freeze**: if any **actionable** AI PR remains open in *any*
   managed repo (not labeled `ai:needs-review`), **inbox triage and
   `issue_to_pr` are blocked fleet-wide**. Manual/terminal PRs
   (`ai:needs-review`) do not freeze unrelated repos.
3. **Inbox triage + intake** (only when the global PR queue is clear): undecided
   issues → triage rules, then deterministic **intake** → `ai:ready` |
   `ai:needs-feedback` | CLOSE/OOS. Path: `issue_triage`
   (`get_issue → triage_issue → intake_issue`). Intake is a deterministic frame
   (shape/playbook fitness, superseded, already-satisfied, ambiguity) — not an
   agent-orchestrator. PR-first freeze still blocks this step fleet-wide when
   actionable AI PRs remain.
4. **PR close-out**: for open AI PRs — conflicts → close + re-ready; failed CI →
   `pr_repair`; mergeable + policy → `pr_triage` (LLM review → merge → close
   issue). Land code before opening new fronts.
   - Same head SHA: do not re-post / re-run LLM review (`already_reviewed_head`).
   - `request_changes` may auto-repair a few times (`limits.max_request_changes_per_pr`,
     default 2); then escalate to `ai:needs-review` (manual terminal).
   - `ai:request-changes` alone is **not** a terminal label; only `ai:needs-review` is.
5. **Implement ready (serial)**: at most one `issue_to_pr` per tick, **only** when
   no actionable AI PR remains globally, and only in a repo with **zero** open AI
   PRs. Before `issue_to_pr`, re-run `lokay-intake-issue --require-ready` so
   READY-without-intake cannot implement (demote/close instead). Then configured
   executor → commit/push → PR. Worktree from `origin/main`. Stuck → ledger →
   `ai:blocked`. Live ready with `executor.enabled: false` is a **stall**.
6. **Health** (honest):
   - `idle` — survey finds no remaining work
   - `progress` — mutations moved the queue this pass
   - `repairing` — active repair / request_changes cycle (not mill-failing)
   - `waiting` — pending CI, review limbo, or only manual PRs
   - `stall` — actionable work with no progress (true stuck / agent disabled)
   - `survey_error` — list atoms failed (refuse false idle)

## Continuous mill

LaunchAgent or:

```bash
export LOKAY_MODE=live
export LOKAY_EXECUTOR_ENABLED=1
export LOKAY_AGENT=pi    # log label only; binary is executor.command in config
export LOKAY_MERGE_ENABLED=1
# LOKAY_REQUIRE_CHECKS=1 default (set 0 only if you accept merge without CI)
uv run lokay-mill --config config.yaml --live --max-passes 8
```

```bash
uv run lokay status --config config.yaml
```

**ok=false** when work remains but mill is not live-ready → NOT WORKING.
`repairing` / `waiting` are ok (honest wait), not recovery thrash.

## Idle rule

May no-op **only** after a full multi-repo survey with **no** remaining actionable work.

## Graphs

See [`GRAPH.md`](GRAPH.md).

- `factory_pass` is the parent Fala run used by the mill; it composes the smaller workflow Falas through a separate journal boundary.
- `pr_review`: structured LLM gate before auto-merge when `merge.require_llm_review`.
  Comments carry a durable `<!-- lokay-review head=… -->` marker for idempotency.
