# Process graph (Fala)

**Order is the product.** Atomic `lokay-*` tools do one job each; Fala declares
which jobs run after which.

## Source of truth

[`fala/lokay.fala-package.toml`](../fala/lokay.fala-package.toml) — `src/lokay/data/lokay.fala-package.toml` is a packaged copy of `fala/` (byte-identical; CI fails if they drift).

### `daemon_cycle` (top-level parent)

```text
recovery_begin
  → recovery_mill
    → recovery_observe
      → recovery_record (persistent 4-of-5 quorum)
        → recovery_incident (skipped until quorum)
          → recovery_run_self_repair (self_repair child Fala)
```

The daemon owns only the singleton lock, health lease and initial carrier
preflight. Fala owns product/recovery order. Every node above is a separate
`lokay-recovery-*` Unix process returning one JSON envelope. A product run that
actually publishes or merges work records no systemic stall fingerprint.

Subprocess atoms pin `cwd` to the Lokay checkout (`PLACEHOLDER_PROJECT`). Fala's
durable host may chdir into `vendor/sqlite.fire` for dylib load; organs must not
inherit that cwd or they emit empty `adapter_failed` and starve the mill.

**Quorum law (narrow recovery):** `recovery_observe` / `recovery_record` mint and
confirm fingerprints only for true product-mill / carrier-class failures
(`stall`, `survey_error`, `plateau`, `budget_exhausted`, hard pass failures).
Empty `adapter_failed` / `subprocess adapter failed` with no product detail is
plumbing, not a confirmed stall — it must not fill the 4-of-5 quorum.
Mill envelopes (and their run-tail events) with `waiting`, `repairing`, `idle`,
`progress`, `offline`, or `overlap` never confirm a stall — so review limbo,
pending CI, and `ai:needs-review` parked PRs cannot steal cycles into
`recovery_run_self_repair`. merge_policy `waiting` / `repair` / `needs_review`
reasons (and nested `pr_merge` soft skips) are never stall evidence either —
trusted auto-merge decisions stay product-side. Soft rows dilute the 4-of-5
window; they do not fill it. `recovery_incident` is skipped until quorum;
incidents reuse the preflight cooldown ledger (`github.incident_cooldown_hours`).

### `factory_pass` (parent)

**Order lives in Fala.** Fleet scheduling is not a fat Python tick. The parent
path conducts one-job atoms; child workflow Falas are started from dispatch
atoms via `run_path`.

```text
host_ff
  → factory_begin
    → survey_prs
      → survey_inbox
        → survey_ready
          → plan_pass
            → dispatch_triage          → issue_triage child Fala
              → resolve_conflicts      → close CONFLICTING/DIRTY + re-ready
                → closeout_prs         → lokay-closeout-pr → pr_repair / pr_triage child Falas
                  → reap_stale_implementing  → leftover in-flight cache → ai:ready
                    → refresh_occupancy  → re-list PRs + live i2pr + just-merged
                      → reap_stale_worktrees → drop leftover corners that cannot resume
                      → select_implement
                      → queue_conflict   → SKIP/CLOSE/READY queue hygiene
                      → dispatch_implement → issue_to_pr child Fala
                        → compute_health
                          → record_pass    → last-pass.json
```

| Atom | One job |
| --- | --- |
| `host_ff` | mill host fetch + ff-only onto origin/main; refuse if dirty / skip-worktree would overwrite |
| `factory_begin` | preflight + pass workspace + budgets |
| `survey_prs` | list open AI PRs for all repos |
| `survey_inbox` | list undecided inbox issues |
| `survey_ready` | list ai:ready; skip those covered by open AI PRs (label stays ready) |
| `plan_pass` | triage targets + closeout set (per-repo PR-first) |
| `dispatch_triage` | run planned `issue_triage` children |
| `resolve_conflicts` | close CONFLICTING/DIRTY AI PRs + re-ready issues |
| `closeout_prs` | for-each remaining AI PRs via `lokay-closeout-pr` |
| `reap_stale_implementing` | leftover in-flight cache → `ai:ready` (mill no longer awards those labels) |
| `refresh_occupancy` | re-list open AI PRs after closeout; union just-merged + live i2pr receipts |
| `reap_stale_worktrees` | drop leftover worktrees that cannot resume (KEEP live i2pr / open PR / dirty unpublished) |
| `select_implement` | clean repos eligible for issue_to_pr (serial K budget; skip occupied) |
| `queue_conflict` | contradiction gate before implement (queue hygiene) |
| `dispatch_implement` | intake gate + `issue_to_pr` (serial by design) |
| `compute_health` | remaining counters + honest mill health |
| `record_pass` | write `last-pass.json` + terminal tick envelope |

**Trust intentional issues:** fleet flow assumes issues from the repo owner /
configured assignee are purposeful. Do not invent new human-approval gates in
the pass spine. Intake `CLOSE` remains for clear obsolete / wrong-shape /
superseded cases only — never bias toward “distrust every ticket.” Goal:
human writes issue → mill delivers.

The mill invokes this parent path (`compose_factory_pass` → `run_path`).
`lokay-factory-tick` is the same parent Fala path — not a second in-process
mill. Parent journal: `~/.lokay/fala/factory/state.sqlite`. Child paths:
`~/.lokay/fala/state.sqlite`. Python `compose/*` may validate CLI contracts and
call `graph_run.run_path`; it must not re-implement fleet scheduling. Do not
grow `compose/*` with GitHub/git/agent logic beyond wiring. Hermes Kanban is not
the ledger for step order.

### `self_repair` (emergency only)

```text
self_repair_prepare (detached exact origin/main)
  → self_repair_run_agent
    → self_repair_validate (full local suite)
      → self_repair_commit
        → self_repair_push_main (fast-forward only, exact unchanged base)
          → self_repair_activate (exact commit)
            → self_repair_preflight (fresh process)
              → self_repair_close
```

Entered only from:

1. **Daemon preflight lane** — Lokay unhealthy, minimal carrier healthy (not
   overlap / not carrier-down); or
2. **`daemon_cycle` stall quorum** — confirmed 4-of-5 hard product-mill failure
   after `recovery_incident` (never from waiting/repairing/review limbo).

It never creates a branch or PR. The coding agent can edit only the detached
worktree; deterministic atoms alone commit and push directly to `main`. A
successful path always returns `restart_required`; product work never resumes in
the stale daemon process.

### `issue_to_pr`

```text
get_issue
  ├─→ assign_issue
  ├─→ stage_implementing   ← no-op on labels: keep ai:ready, strip leftover cache
  └─→ make_branch
        └─→ worktree_add
              └─→ plan_issue   ← deterministic approach.md (trust-with-evidence)
                    └─→ localize     ← Agentless file-before-patch path list
                          └─→ run_agent     ← only non-deterministic coding node
                                └─→ commit_all
                                      └─→ rebase_onto_base  ← fetch + rebase onto origin/main; conflict = fail closed (no dirty PR)
                                            └─→ test_local   ← local pytest; skip if no suite
                                            ├─ (red, recorded) → repair_agent   ← ONE patch from the test log (K=1)
                                            │                      └─→ test_local_recheck
                                            └─→ assert_real_diff ← refuse plan/localize-only diffs
                                                  └─→ push            ← only after green / honest skip (recheck if nest ran)
                                                        └─→ pr_create   ← only after successful push; never off a red suite or plan-only diff
                                                              └─→ stage_pr_open   ← no-op on labels: keep ai:ready
                                                                    └─→ list_prs
                                                                          └─→ pr_label
```

`plan_issue` (`lokay-plan-issue`) writes `.lokay/approach.md` in the worktree
**before** `run_agent`: goal, files likely touched, test plan, non-goals.
Mostly deterministic extraction from the issue body (+ path hints). Optional
`--llm` assist is skippable and fail-closed when requested without a configured
slot. This is **evidence for intentional issues**, not a human approval gate and
not `NEEDS_HUMAN` by default. Later `pr_review` may compare the diff to the plan
as a soft signal (missing/misaligned approach → `nits` only).

`localize` (`lokay-localize`) is a separate deterministic atom (Agentless
localization → repair → validation): seed text (issue + approach.md) plus the
worktree tree → non-empty edit path list (written to `.lokay/localize.json`).
Fala conducts it **before** `run_agent`. Empty list fails closed — the agent
does not start. Not an embedding service and not a second planner; one job:
paths. The agent prompt receives that scope so patches stay on listed files/
directories instead of roaming the full checkout.

### `issue_triage` (inbox → labels / split)

```text
get_issue
  └─→ triage_issue   ← pure rules → ready | split | rare needs-feedback | OOS close
        └─→ intake_issue  ← deterministic intake → CLOSE | READY | SPLIT | NEEDS_HUMAN
              └─→ issue_split  ← when SPLIT: create bounded children (gh + rules)
```

**Minimize human in the loop:** CLOSE / SPLIT / READY+implement are the exits.
`NEEDS_HUMAN` / `ai:needs-feedback` is residual after rules fail closed — not the
default for oversized work.

`ai:ready` is an **outcome** of triage **plus intake**, not the start of the universe.
Intake runs cheap checks first (still-open, superseded/merged PR, duplicate AI PR
for the same issue, playbook/shape fitness on library/kit/empty/Swift-only,
already-satisfied / feature-present paths, size → SPLIT). CLOSE posts a short
actionable receipt (and drops `ai:ready`). SPLIT queues `issue_split`, which
creates bounded child issues, labels the parent `ai:tracker`, and closes the
parent as a tracker — parent is never left `ai:ready`. Children re-enter
inbox/intake on later passes. NEEDS_HUMAN applies `ai:needs-feedback` only when
split is impossible or evidence is inconclusive. Per-repo PR-first:
triage/intake/split mutations skip a repo that still has actionable open AI PRs
(or a failed PR survey for that repo); other clean repos continue. Intake still
runs inside `issue_triage` whenever triage is allowed; the mill also runs
`queue_conflict` (queue hygiene — not a parallel scheduler) then re-runs
`intake_issue` with `--require-ready` before every `issue_to_pr`. **Serial by
design:** default `limits.max_issue_to_pr_per_pass` is **1** (ticket after
ticket). K is an optional pass budget, not concurrent worktrees/Pi/tmux.

### `pr_repair` (red checks on open ai/fix PR)

```text
pr_checks
  └─→ stage_repairing   ← no-op on labels: keep ai:ready
        └─→ worktree_add
              └─→ localize    ← paths from checks/review seed + tree
                    └─→ run_agent   ← repair prompt (only non-deterministic node)
                          └─→ commit_all
                                └─→ test_local   ← local pytest; skip if no suite
                                      └─→ assert_real_diff
                                            └─→ push   ← published tip; never rebase (force-push forbidden)
```

### `pr_triage` (merge policy → close issue)

```text
pr_checks
  └─→ pr_review    ← structured harness review via run_agent (fail closed)
        └─→ worktree_add   ← PR branch tip (no reset onto main; no coding agent)
              └─→ test_local   ← local pytest; skip if no suite; red fails closed
                    └─→ pr_merge     ← skipped when checks not mergeable / review not approve / merge disabled
                          └─→ stage_clear   ← clear issue ledger labels after merge
                                └─→ close_issue   ← issue# from ai/fix/N-* branch when known
```

`pr_review` is fail-closed: invalid JSON, `request_changes`, `needs_human`, or `secrets=true` never auto-merges.
Trusted auto-merge (`lokay.merge_policy`): with `merge.enabled` / `LOKAY_MERGE_ENABLED`,
approve + green checks + local tests → `pr_merge` + `close_issue` in one path; pending → waiting;
red → repair; secrets / `needs_human` / escalated `ai:needs-review` never merge.
Soft documentation nits must not route to `ai:needs-review`.
Presence / light alignment of `.lokay/approach.md` is a soft review signal only —
never invent a human gate from a missing plan file.
Config: `merge.require_llm_review` (default true), `merge.require_checks` (default false).
Env: `LOKAY_REQUIRE_LLM_REVIEW`, `LOKAY_REQUIRE_CHECKS`, `LOKAY_MERGE_ENABLED`.

`resolve_conflicts` handles **merge conflicts**: `mergeable=CONFLICTING|DIRTY`
→ `lokay-pr-close` + re-label linked issue `ai:ready` so the next pass re-runs
`issue_to_pr` from current main (one stuck conflict must not freeze the mill).

- **conduction** edges = dependencies (Fala will not ready a node until upstream succeeded).
- **push** / **pr_merge** / **pr_create** also fail closed in the organ unless `test_local` conduction is ok (skip / `no_python_test_suite` counts). `pr_create` additionally requires a successful `push`. `push` / `pr_create` also require `assert_real_diff`: a diff that is only `.lokay/approach.md` / `.lokay/localize.json` is not progress and never opens a PR.
- **issue_to_pr red suite** does **not** open a PR. One bounded AlphaCodium nest runs instead: `test_local` (first probe, records red so Fala can continue) → `repair_agent` (K=1 patch from the test log) → `test_local_recheck`. Recheck green → push → pr_create. Recheck red / zero-diff / agent fail → path fails closed (`local_repair_exhausted`); the mill marks that seed stuck and takes the next one. There is no third attempt and no `gh pr create` off a red suite.
- **run_agent** is the only non-deterministic coding slot — external harness via `executor.command`/`args` (no vendor hardcode). See [`NO_STUBS.md`](NO_STUBS.md). For a seed classified separately as unbounded collection work, this slot receives a collector boundary: make only the bounded bootstrap patch; the deployed collector starts durably in the background after merge. Pi and the mill do not populate collection data or wait for completion.
- **plan_issue** is deterministic evidence before that coding slot.
- **localize** is deterministic Agentless path selection immediately before the
  coding slot (serial path: `worktree_add → plan_issue → localize → run_agent`).
  Missing/empty localize fails closed in the organ — agent does not start.
  `plan_issue.files_likely` is passed as `--extra-path`. Weak token hits do not
  pad the list to 40; a long list is a hint in the prompt, not a cage.
- **run_agent timeout** (executor 1800s) is incomplete, not a graph hard-fail.
  The leftover tree is kept; `repair_agent` resumes the same corner / session
  once (K=1). Do not raise 1800 on the first shot.
- **Published-tip retry** (`origin/<branch>` exists — including a closed
  CONFLICTING tip that matches HEAD) resets the corner from `origin/<base>`
  and deletes the stale remote tip. KEEP only unpublished ahead that already
  contains `origin/<base>`, or a dirty leftover. Unpublished-but-behind-main
  (rebase_conflict leftover) also RESET — replaying those commits loops.
  Never force-push.
- **Miss harvest** (`factory_begin` → `harvest_fail_closed_children`): `plan_only`
  / `zero_diff` / `rebase_conflict` leave the slot after **3** unique `run_id`s;
  `push_failed` after **2**. A stale ledger row already `blocked` at 1 is
  reconciled from the journal — harvest reopens the slot until unique-run N.
  Crash reasons (`local_repair_exhausted`, red recheck, bad ref) still block at
  1 and stay buried. Harvest does not CLOSE the issue. The repo mutex must not
  stay on one corpse.
- Everything else is deterministic (`gh` / `git` / pure functions).

## Run

```bash
# inspect graph
uv run lokay path --describe
# or: uv run lokay-run-path --describe

# execute (Fala host + organ → atoms)
uv run lokay-run-path --config config.yaml --path issue_to_pr \
  --repo mikolaj92/lokay --issue 1
# live mutations:
uv run lokay-run-path --config config.yaml --path issue_to_pr \
  --repo mikolaj92/lokay --issue 1 --live
```

Journal: `~/.lokay/fala/state.sqlite`  
Materialized package: `~/.lokay/fala/lokay.fala-package.toml`  
(`uv run --project <checkout>` filled in for every organ — never bare `python3`)

## Bridge

| Piece | Role |
| --- | --- |
| `fala/lokay.fala-package.toml` | graph |
| `lokay.fala_organ` | one Fala subprocess organ → one atom |
| `lokay.graph_run` | `host_run_package` wrapper |
| `lokay-*` procs | Unix atoms |

Do not put graph order in the coding harness. Do not reintroduce Hermes Kanban as the ledger for step order.

**Runtime note:** Fala is the only workflow composer. Python composers validate the public command contract, invoke
`lokay.graph_run.run_path`, and normalize Fala's terminal per-effector outputs.
`compose_mill` repeats the parent `factory_pass`; it does not invoke child paths
directly. Atomic `lokay-*` processes remain the execution
boundary, but there is no runtime Python fallback graph or engine-selection flag.
