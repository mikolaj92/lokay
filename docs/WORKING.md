# WORKING machine (Definition of Done)

Lokay is **working** only if it continuously mills **all** work across
configured repos (`repos.mikolaj92.yaml`). Order: survey → **per-repo PR-first**
(close-out) → inbox triage / implement in repos with no open AI PR. Agent must
be **real** ([`NO_STUBS.md`](NO_STUBS.md)). Minimize human: humans write issues;
the mill consumes them to merged results — do not add new human gates.

## Product law: minimize human in the loop

Humans **author issues**. The system should **CLOSE**, **SPLIT**, or
**READY+implement**. `NEEDS_HUMAN` / `ai:needs-feedback` is a **rare residual**
after deterministic rules fail closed — never the default escape hatch for
oversized or ambiguous work that can be auto-split.

`lokay status --human` lists that residual mailbox across managed repos. It is
**exception reporting**, not a workflow step. The mill does **not** wait on a
human digest and does **not** freeze other repos because one issue is parked
`ai:needs-feedback` or a PR is `ai:needs-review`.

## Full pass (one tick)

1. **Survey** every managed repo: inbox, `ai:ready`, open `ai/fix/*` PRs.
2. **Per-repo PR-first**: PR close-out (conflict / repair / triage / waiting) is
   scoped to each repository. An **actionable** AI PR in repo A does **not**
   freeze inbox triage or `issue_to_pr` in repo B. Manual/terminal PRs
   (`ai:needs-review`) never freeze unrelated repos. Issue-level
   `ai:needs-feedback` never freezes any repo. Safety: never open a second
   `ai/fix/*` PR in a repo that already has an open AI PR.
3. **Inbox triage + intake + optional split** (per repo, when that repo has no
   actionable open AI PR and its PR survey succeeded): undecided issues →
   triage rules, then deterministic **intake** → `CLOSE` | `READY` | `SPLIT` |
   rare `NEEDS_HUMAN`. Path: `issue_triage`
   (`get_issue → triage_issue → intake_issue → issue_split`). Intake is a
   deterministic frame (shape/playbook fitness, superseded, duplicate AI PR,
   already-satisfied / feature-present, size → split) — not an
   agent-orchestrator. Oversized / multi-epic / inventory blobs **auto-split**
   into bounded child issues (parent becomes `ai:tracker`, not `ai:ready`).
   Children re-enter inbox/intake on later passes. Fail closed: a failed PR
   survey for a repo refuses triage mutations **in that repo only**.
4. **PR close-out**: for open AI PRs — conflicts → close + re-ready; failed CI →
   `pr_repair`; mergeable + policy → `pr_triage` (LLM review → merge → close
   issue). Land code in a repo before opening a new front there.
   - Same head SHA: do not re-post / re-run LLM review (`already_reviewed_head`).
   - `request_changes` may auto-repair a few times (`limits.max_request_changes_per_pr`,
     default 2); then escalate to `ai:needs-review` (manual terminal).
   - `ai:request-changes` alone is **not** a terminal label; only `ai:needs-review` is.
5. **Implement ready (parallel K)**: up to **K** `issue_to_pr` runs per factory
   pass across **different** clean repos (`limits.max_issue_to_pr_per_pass`,
   default 3; legacy alias `max_issues_per_tick`). Still **serial within a
   repo** (at most one attempt / one open AI PR per repo). A stuck or PR-busy
   repo must not block ready work in other clean repos. Before `issue_to_pr`,
   re-run `lokay-intake-issue --require-ready` so READY-without-intake cannot
   implement (demote/close/split instead). Then configured executor → commit/push →
   PR. Worktree from `origin/main`. Stuck → ledger → `ai:blocked`. Live ready
   with `executor.enabled: false` is a **stall**.
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
uv run lokay status --config config.yaml --human   # residual mailbox only
```

**ok=false** when work remains but mill is not live-ready → NOT WORKING.
`repairing` / `waiting` are ok (honest wait), not recovery thrash.
`--human` does not set mill not-working; it only lists residuals.

## Idle rule

May no-op **only** after a full multi-repo survey with **no** remaining actionable work.

## Graphs

See [`GRAPH.md`](GRAPH.md).

- `factory_pass` is the parent Fala run used by the mill; it composes the smaller workflow Falas through a separate journal boundary.
- `pr_review`: structured LLM gate before auto-merge when `merge.require_llm_review`.
  Comments carry a durable `<!-- lokay-review head=… -->` marker for idempotency.
