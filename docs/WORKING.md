# WORKING machine (Definition of Done)

Lokay is **working** only if it continuously mills **all** work across
configured repos (`repos.mikolaj92.yaml`). Order: survey → **per-repo PR-first**
(close-out) → inbox triage / implement in repos with no open AI PR. Agent must
be **real** ([`NO_STUBS.md`](NO_STUBS.md)). Minimize human: humans write issues;
the mill consumes them to merged results — do not add new human gates.

For the autonomous mill Definition of Working (pass promises, night profile,
hermetic canaries, how to read `lokay status` / `last-pass.json`), see
[`AUTONOMY.md`](AUTONOMY.md).

## Issue ledger = chat with the mill

Operators should read **GitHub Issues** (labels + optional short receipts), not
chat, to see where Lokay is. Exclusive stage labels:

| Stage | Label | When |
| --- | --- | --- |
| ready | `ai:ready` | Intake READY (implementable) |
| implementing | `ai:in-progress` | `issue_to_pr` running |
| pr-open | `ai:pr-open` | PR created / covering open AI PR |
| ci-waiting | `ai:ci-waiting` | Checks pending |
| repairing | `ai:repairing` | `pr_repair` in flight |
| (terminal) | clear + close | After merge — issue closed |

Reuse parking / residual labels unchanged: `ai:blocked`, `ai:needs-feedback`,
`ai:needs-review`, `ai:tracker`. Atom: `lokay-stage-label`. Diagram:
[`AUTONOMY.md`](AUTONOMY.md#issue-ledger--chat-with-the-mill).

## Product law: minimize human in the loop

**Humans author intentional issues; the mill consumes.** Trust the issue author:
when the issue is created or owned by the trusted operator (`github.assignee`,
default mikolaj92), assume it makes sense — prefer **READY+implement** autonomy.
Do not add distrustful human gates or clarification parking for ordinary
operator-authored work. Deeper skepticism is for foreign/external authors if
distinguished at all.

The system should **CLOSE**, **SPLIT**, or **READY+implement**. Maximize
autonomy. `NEEDS_HUMAN` / `ai:needs-feedback` is a **rare residual** after
deterministic rules fail closed — never the default escape hatch for oversized
or ambiguous work that can be auto-split.

`lokay status --human` lists that residual mailbox across managed repos. It is
**exception reporting**, not a workflow step. The mill does **not** wait on a
human digest and does **not** freeze other repos because one issue is parked
`ai:needs-feedback` or a PR is `ai:needs-review`.

Light glance metrics from `last-pass.json` (ready / PR / mergeable / progress)
are fine observability — not a metrics product. See [`AUTONOMY.md`](AUTONOMY.md).

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
5. **Implement ready (serial by design)**: one ticket after another. `K` /
   `limits.max_issue_to_pr_per_pass` (default **1**; legacy alias
   `max_issues_per_tick`) is an **optional pass budget**, not concurrent
   worktrees / Pi / tmux. At most one attempt / one open AI PR per repo.
   `K>1` remains configurable as rare breadth across already-isolated clean
   repos — not the recommended default. Before `issue_to_pr`,
   `lokay-queue-conflict` demotes/defers clear contradictions (open AI PR
   covering the same issue, epic with children, unmet Depends on / Blocked by,
   obvious path overlap), then `lokay-intake-issue --require-ready` so
   READY-without-intake cannot implement. Inside `issue_to_pr`: worktree from
   `origin/main` → **`plan_issue`** (`.lokay/approach.md` evidence) →
   configured executor → commit/push → PR. The plan atom is trust-with-evidence,
   not a human gate. Stuck → ledger → `ai:blocked`. Live ready with
   `executor.enabled: false` is a **stall**.
6. **Health** (honest):
   - `idle` — survey finds no remaining work
   - `progress` — mutations moved the queue this pass
   - `repairing` — active repair / request_changes cycle (not mill-failing)
   - `waiting` — pending CI, no-CI while `require_checks`, review limbo,
     green PRs while `merge.enabled` false (`remaining.merge_disabled`), or
     only manual PRs (same soft matrix as `merge_policy`)
   - `stall` — actionable work with no progress (true stuck / agent disabled;
     not merge-disarmed green)
   - `survey_error` — list atoms failed (refuse false idle)

## Continuous mill

LaunchAgent (cron heartbeat) **and** optional GitHub event wake. Cron keeps
the mill turning; event wake (`lokay-wake` on a self-hosted `lokay-mill`
runner) reacts when an issue opens / is labeled `ai:ready` or when PR checks
complete. Same serial mill (K=1), same lock — not a parallel fleet. Details:
[`AUTONOMY.md`](AUTONOMY.md#event-wake-vs-cron).

LaunchAgent or:

```bash
export LOKAY_MODE=live
export LOKAY_EXECUTOR_ENABLED=1
export LOKAY_AGENT=pi    # log label only; binary is executor.command in config
export LOKAY_MERGE_ENABLED=1          # trusted auto-merge when green + approved
export LOKAY_REQUIRE_CHECKS=1         # pending/none wait; red → repair (recommended live)
export LOKAY_REQUIRE_LLM_REVIEW=1     # default; approve/merge_ok before merge
uv run lokay-mill --config config.yaml --live --max-passes 8
```

Merge policy (fail closed): with `merge.enabled` / `LOKAY_MERGE_ENABLED`, the mill
merges in the same `pr_triage` pass when checks are green (honoring `require_checks`),
LLM review is `approve` / `merge_ok`, and there are no secrets, `needs_human`, or
escalated `ai:needs-review`. Pending checks → `waiting` (not stall). Merge disabled
while green → `waiting` / `remaining.merge_disabled` (not stall). Red checks →
repair. Soft documentation nits stay on the approve path — they must not park a PR
for a person.

```bash
uv run lokay status --config config.yaml
uv run lokay status --config config.yaml --human   # residual mailbox only
uv run lokay status --config config.yaml --local   # readiness + last_pass
```

Status JSON includes `health`, merge knobs (`merge_enabled`, `require_checks`,
`require_llm_review`), `k` / `max_issue_to_pr_per_pass`, per-repo `by_repo`
(actionable PRs / ready / inbox), and compact `human_residuals`. Each tick also
writes `~/.lokay/last-pass.json` (or `<state_dir>/last-pass.json`). See
[`MILL_HEALTH.md`](MILL_HEALTH.md).

**ok=false** when work remains but mill is not live-ready → NOT WORKING.
`repairing` / `waiting` are ok (honest wait), not recovery thrash.
`--human` does not set mill not-working; it only lists residuals.

## Self-repair / recovery (narrow)

Self-repair must **not** steal cycles from normal review limbo or per-repo waiting.
Product mill time wins over emergency recovery.

**Self-repair may run only when:**

1. **Preflight lane** — daemon preflight proves Lokay unhealthy while the
   minimal carrier remains healthy (not overlap, not carrier-down). Or
2. **Product-stall quorum** — `daemon_cycle` observes a true product-mill /
   carrier-class failure fingerprint in **4 of the last 5** runs
   (`recovery-history.json`), then files one deduplicated incident and enters
   the `self_repair` child Fala.

**Never mint a systemic stall fingerprint / never fill the 4-of-5 quorum for:**

- mill `health=waiting` (pending CI, merge-disarmed green, review limbo, only
  manual/`ai:needs-review` PRs)
- mill `health=repairing` (active repair / request_changes cycle)
- other honest soft outcomes (`idle`, `progress`, `offline`, `overlap`)
- per-event `pr_repair` / `issue_to_pr` / `pr_triage` failures while the mill
  envelope itself is still a soft wait above

Soft observations may sit in the rolling window (they **dilute** quorum) but
cannot count as matching failure fingerprints. Confirmed-stall incidents share
the same `github.incident_cooldown_hours` / ledger as preflight incidents.

## Idle rule

May no-op **only** after a full multi-repo survey with **no** remaining actionable work.

## Graphs

See [`GRAPH.md`](GRAPH.md).

**Law:** order lives in Fala; work is small Unix one-job processes; no Hermes
Kanban ledger; do not grow `compose/*` with GitHub/git/agent scheduling.

- `factory_pass` is the parent Fala run used by the mill. It conducts
  `factory_begin → survey_prs → survey_inbox → survey_ready → plan_pass →
  dispatch_triage → resolve_conflicts → closeout_prs → select_implement →
  queue_conflict → dispatch_implement → compute_health → record_pass`.
  Dispatch atoms start the smaller workflow Falas through a separate journal
  boundary.
  `compose/tick.py` is a thin in-process bridge for `lokay-tick` / autonomy
  canaries — not the multi-repo brain.
- `pr_review`: structured LLM gate before auto-merge when `merge.require_llm_review`.
  Comments carry a durable `<!-- lokay-review head=… -->` marker for idempotency.
- Env knobs (see `config.example.yaml`): `LOKAY_MERGE_ENABLED`, `LOKAY_REQUIRE_CHECKS`,
  `LOKAY_REQUIRE_LLM_REVIEW`. Keep `merge.enabled: false` in dry-run configs; enable
  merge on the live mill via env.
