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
A live mill with a fresh empty-survey stamp and idle last-pass skips hosting
this parent path; leftover closeout still runs, mill stuck is still
harvested, CLOSED leftover mill worktrees are still reaped, leftover-ready
still runs, and leftover-cache still runs.
Idle CLASSIFY_CAP skips no-issue leftovers so Fala cannot starve mill issues.
Idle CLASSIFY_CAP skips dirty-real leftovers so KEEP cannot starve mill issues.
Harvest leftovers are not mill issues. Idle CLASSIFY_CAP reaps empty
no-issue leftovers so harvest leftovers cannot freeze mill porcelain.
Idle KEEP-only leftovers still write the over-cap stamp.
Idle worktree removal requires healthy. Classification and KEEP stamping do not. Hosted worktree removal also requires healthy; hosted KEEP classification does not.
Idle over-cap skip outlives leftover-probe.
Nested clones are not mill leftover
worktrees. Mill worktrees keep a .git file.
`uv.lock`-only is not real uncommitted content. After the
stamp expires, a cheap GitHub probe of mill PR / inbox / ready lists
refreshes the stamp and skips Fala when all three are still empty. Probe
failure or remaining work hosts. Missing stamp, occupied last-pass, or
pytest always hosts. mill-daemon skips caretaker `lokay-host-ff` when GitHub
`main` already matches HEAD and `origin/main`. Fresh idle stamps skip python
`host_ff_already_current` and the GitHub SHA probe. Fresh idle stamp age
reuses one date +%s. Busy lock still
probes. Probe failure or SHA mismatch still runs host-ff. Local clones
still run host-ff. Small mill / launchd logs skip
python truncate. Small launchd stdio skips python inode reopen; fat logs
still bound in place, then reopen. Fresh idle skip defers the first
launchd stdio bound; hosted/probe ticks still bound. Fresh idle skip
defers caretaker plist write; hosted/probe ticks still write. Missing or XML plist skips python
`launchd_stdout_paths`; binary plist still python. Fat truncate leaves
1KiB glance headroom so later idle lines stay under the cap. When
last-pass is idle, it skips `lokay-daemon` while empty-survey and
leftover-closeout stamps are fresh; mill-daemon skips python
`idle_skip_daemon` on that path. After
leftover-stamp expiry, a cheap empty GitHub probe of CLOSED
`work:ready` / `ai:ready` mill issues refreshes that stamp. Fresh leftover skip does not require healthy. Hosted leftover parks still do.
Hosted unbounded parks require healthy. Planned parks do not.
Hosted merge-now merges require healthy. Planned merges do not.
Leftover-probe
still hosts `lokay-daemon` so idle reap continues. Leftover-probe still
hosts `lokay-daemon` even when mill-probe would also run.
Leftover-probe host skips GitHub `/user` this tick. Hosted ticks without
leftover lists still probe.
Leftover-probe skips GitHub SHA when survey stamp is still fresh.
Mill-probe skips GitHub SHA when leftover stamp is still fresh.
Combined leftover+survey expiry still probes SHA. One batched GraphQL read
probes both CLOSED ready labels. After survey-stamp expiry, one batched GraphQL read probes mill PR / inbox /
ready state and refreshes the survey stamp. GraphQL idle-skip does not import ThreadPoolExecutor.
Pagination, malformed data, or
probe failure still hosts.
Probe failure, remaining leftovers, occupied last-pass, digest mismatch,
or host-ff update still starts the daemon. Fresh idle skip with a persisted
digest skips `checkout_digest` and `package_matches`. An `already_current`
host-ff envelope skips python `host_ff_updated`. Fresh idle skip writes the
launchd glance in bash and skips python `emit_launchd_glance` plus extra
`bound_launchd_stdio`. Hosted ticks still scrape the mill log and bound
launchd stdio around glance. Already under keep skips python `prune_mill_logs`.
Fat mill-log dirs still prune. mill-daemon caches `python3` so later `_python`
helpers skip `command -v`. Probe skip, missing digest, host-ff update, or a
hosted daemon still checks the wheel.

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
          → ready_hygiene       → remove legacy ai:ready without work:ready
            → plan_pass
            → dispatch_triage          → issue_triage child Fala
              → resolve_conflicts      → close CONFLICTING/DIRTY + re-ready
                → closeout_prs         → lokay-closeout-pr → pr_repair / pr_triage child Falas
                  → reap_stale_implementing  → leftover in-flight cache → ai:ready
                    → reap_over_budget  → kill plan_only over budget; harvest real diff to PR
                    → refresh_occupancy  → occupy live/merged; re-list leftover-ready only
                      → reap_stale_worktrees → drop leftover corners that cannot resume
                      → select_implement
                      → queue_conflict   → SKIP/CLOSE/READY queue hygiene
                      → dispatch_implement → issue_to_pr child Fala
                        → compute_health
                          → compact_state  → bound the existing state.jsonl
                            → record_pass  → last-pass.json
```

| Atom | One job |
| --- | --- |
| `host_ff` | mill host fetch + ff-only onto origin/main; refuse if dirty / host catalog skip-worktree would overwrite. Product `config.yaml` follows origin/main. Launchd caretaker skips the mill pass when `mill.lock` is held. After ff moves HEAD, mill-daemon reinstalls and starts `lokay-daemon` in the same tick; live i2pr is not killed. Crash KeepAlive (`SuccessfulExit=false`) restarts a failed tick without waiting StartInterval; idle 0 stays on the 60s heartbeat. Already 60s crash KeepAlive skips python `plistlib`; missing plists stay missing. Delayed `--install` double-forks out of the launchd process group so idle 0 cannot kill the reload. Trailing delayed `--install` checks keepalive stamp before `mill_lock_busy`. After caretaker `lokay-host-ff`, mill-daemon sets `LOKAY_HOST_FF_FETCHED=1` so in-cycle `host_ff` does not fetch origin/main twice and preflight skips a second `ls-remote`. Caretaker `lokay-host-ff` skips `git fetch origin/main` when GitHub `main` matches local `origin/main`. Probe failure or SHA mismatch still fetches. Every Fala inherit_env lists that key; nested `recovery_mill` must not drop it. Standalone `lokay-daemon` still probes |
| `factory_begin` | preflight + pass workspace + budgets; refuse when in-cycle `host_ff` just updated **or** `LOKAY_PROCESS_HEAD` drifted (restart, do not mill on the previous import). Auth probe must not treat a GitHub `/user` 503 as a missing token. Healthy first host check is not rerun (`gh api user` / ast.parse). Repair still reruns `_check`. Healthy preflight closes leftover `<!-- lokay-preflight:… -->` tickets. After an empty leftover-incident probe, skip that GitHub list for 300s without refreshing the stamp. Fresh leftover-incident skip is not applied. Leftover-incident skip reports planned=not live. Empty leftover-incident host is not applied. Empty leftover-incident host reports planned=not live. Leftover-incident probe failure reports probe_failed. Leftover-incident probe failure reports planned=not live. Leftover-incident ImportError is not applied. Leftover-incident ImportError reports planned=not live. Leftover-incident empty name is not applied. Leftover-incident empty name reports planned=not live. Leftover-incident OSError is not applied. Leftover-incident OSError reports planned=not live. Leftover-incident host reports probe_failed. Idle leftover-incident skip outlives leftover-probe. Hosted factory_pass stays at 300s. Pytest must not skip leftover-incident GitHub lists using the mill stamp. |
| `survey_prs` | list open AI PRs for all repos (full page; cap is survey_error). After a complete empty mill survey, skip GitHub lists for 120s without refreshing the stamp. A live mill with that fresh stamp and idle last-pass also skips hosting `factory_pass` and parent `daemon_cycle` Fala. After the stamp expires, a cheap GitHub probe refreshes it and skips Fala when PR / inbox / ready are still empty. Leftover closeout still runs after that skip. Pytest must not skip GitHub surveys using the mill stamp. |
| `survey_inbox` | list undecided inbox issues (full page; cap is survey_error). Shares the 120s empty-survey stamp with `survey_prs` / `survey_ready`. Inbox rate limit does not stamp empty. |
| `survey_ready` | list implementable `work:ready` (intake/triage/stage award it with `ai:ready`); skip those covered by open AI PRs. Missing `state` is still OPEN ready; only explicit CLOSED parks. After a complete empty mill survey, skip GitHub lists for 120s without refreshing the stamp. |
| `ready_hygiene` | remove leftover `ai:ready` from issues without `work:ready`. READY awards both labels. After an empty leftover-ready probe, skip that GitHub list for 300s without refreshing the stamp. Fresh leftover-ready skip does not require healthy. Fresh leftover-ready skip is not applied. Hosted leftover-ready parks still do. Unhealthy leftover-ready still lists GitHub. Unhealthy leftover-ready parks are planned. Empty leftover-ready host is not applied. Leftover-ready rate limit does not stamp empty. Idle leftover-ready skip outlives leftover-probe. Hosted factory_pass stays at 300s. Idle daemon_cycle skip still runs leftover-ready. Pytest must not skip leftover-ready GitHub lists using the mill stamp. |
| `plan_pass` | triage targets + closeout set (per-repo PR-first) |
| `dispatch_triage` | run planned `issue_triage` children. Preflight incident tickets (`<!-- lokay-preflight:… -->`) are `ai:blocked`, not `work:ready`. A later healthy preflight closes those leftover tickets |
| `resolve_conflicts` | close CONFLICTING/DIRTY AI PRs + re-ready issues |
| `closeout_prs` | for-each remaining AI PRs via `lokay-closeout-pr` |
| `reap_stale_implementing` | leftover in-flight cache → `ai:ready` (mill no longer awards those labels). After an empty leftover-cache probe, skip those GitHub lists for 300s without refreshing the stamp. Fresh leftover-cache skip does not require healthy. Fresh leftover-cache skip is not applied. Hosted leftover-cache parks do. Unhealthy leftover-cache parks do not clear the stamp. Unhealthy leftover-cache parks are planned. Leftover-cache reaped_count excludes planned parks. Hosted leftover-cache reports applied. Leftover-cache rate limit does not stamp empty. Idle leftover-cache skip outlives leftover-probe. Hosted factory_pass stays at 300s. Idle daemon_cycle skip still runs leftover-cache. Pytest must not skip leftover-cache GitHub lists using the mill stamp. |
| `reap_over_budget` | kill over-budget plan_only i2pr and park the slot. A live coder with a **real** diff is harvested (`commit_all` → `push` → `pr_create`) without SIGTERM |
| `refresh_occupancy` | union just-merged + live i2pr; re-list PRs only on leftover-ready repos that are not occupied. A live receipt whose process command is unreadable remains occupied; an unreadable lifecycle receipt occupies every configured repo. Unknown is not idle. A `reaped` receipt is idle even if pi has not exited |
| `reap_stale_worktrees` | drop leftover worktrees that cannot resume (KEEP live i2pr / occupancy / `pr_survey_failed` / open PR / dirty unpublished; one `ls-remote` per repo). Over-cap stacks view at most 4 oldest issues; after a no-reap over_cap, skip those GitHub views for 300s without refreshing the stamp. Pytest must not skip over-cap GitHub views using the mill stamp. Failed PR survey, local process uncertainty, or receipt state is unknown, not idle; receipt uncertainty keeps every corner. |
| `select_implement` | clean repos eligible for issue_to_pr (serial K budget; skip occupied). Live mini mill (`mill_scope`) delivers `mikolaj92/lokay` only |
| `queue_conflict` | contradiction gate before implement (queue hygiene) |
| `dispatch_implement` | intake gate + `issue_to_pr` (serial by design). If its live `ps` mutex survey fails, it refuses every launch: unknown is not idle. `plan_only` parks the slot; it does not CLOSE the issue. |
| `compute_health` | remaining counters + honest mill health (ready behind PR-first / occupancy is waiting, not stall) |
| `record_pass` | write `last-pass.json` + terminal tick envelope |
| `compact_state` | atomically shrink the existing JSONL to recovery/yield facts when it exceeds 8 MiB |
| mill Fala journals | idle mill sqlite under `~/.lokay/fala/{daemon-cycle,factory}` rotates when oversized; recovery stays on `state.jsonl`. Live `fala/i2pr/` journals stay |
| leftover closeout | after each factory pass, park leftover `work:ready`/`ai:ready` on GitHub-CLOSED mill issues. Do not paginate every mill PR to prove a closer. After an empty leftover, skip those GitHub lists for 300s. Fresh leftover skip does not require healthy. Fresh leftover-closeout skip is not applied. Leftover-closeout skip reports planned=not live. Hosted leftover parks still do. Unhealthy leftover-closeout still lists GitHub. Unhealthy leftover-closeout parks are planned. Hosted leftover-closeout reports applied. Empty leftover-closeout host is not applied. Leftover-closeout rate limit does not stamp empty. Pytest must not skip leftover GitHub lists using the mill stamp. |

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
worktree; deterministic atoms alone commit and push directly to `main`. The
`self_repair_run_agent` coding slot uses the same bounded 1800-second budget as
other agent paths. A successful path always returns `restart_required`; product
work never resumes in the stale daemon process.

### `issue_to_pr`

Detached launch uses a durable `starting` receipt before `Popen`, then a
private activation pipe: the child cannot enter this graph until its matching
PID receipt is atomically published. If the launcher dies in that interval,
EOF makes the gated child exit before any worktree action; a later pass may
recover only that pipe-gated reservation after confirming the launcher is dead.
Malformed and pre-barrier reservations remain unknown/live and preserve the
fail-closed occupancy/reap boundary. PID command inspection uses wide `ps` so
macOS truncation cannot turn a live child into a stale worktree candidate.

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
not `NEEDS_HUMAN` by default. `pr_review` is blind to that plan: the reviewer
sees ticket + code diff + tests, not `.lokay/approach.md` and not a
compare-to-plan instruction.

`localize` (`lokay-localize`) remains one job: a non-empty edit path list
written to `.lokay/localize.json` before `run_agent`. If that file already
has paths, skip the localize executor and start `run_agent`. Live mode asks the
configured executor for a structured path proposal; Python still validates
against the tree, keeps extra/seed paths, and fails closed on an empty list.
Invalid JSON / timeout falls back to the deterministic scorer. Not an
embedding service and not a second planner.

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
Hard facts stay deterministic (still-open, superseded/merged PR, duplicate AI PR
for the same issue). Semantic remainder — shape, already-satisfied, size/SPLIT,
essence — is one structured executor call; invalid JSON / timeout falls back to
the previous regex/heuristic frame. CLOSE posts a short actionable receipt (and
drops `ai:ready`). SPLIT queues `issue_split`, which creates bounded child
issues, labels the parent `ai:tracker`, and closes the parent as a tracker —
parent is never left `ai:ready`. Children re-enter inbox/intake on later passes.
NEEDS_HUMAN applies `ai:needs-feedback` only when split is impossible or evidence
is inconclusive. Per-repo PR-first: triage/intake/split mutations skip a repo
that still has actionable open AI PRs (or a failed PR survey for that repo);
other clean repos continue. Intake still runs inside `issue_triage` whenever
triage is allowed; the mill also runs `queue_conflict` (queue hygiene — not a
parallel scheduler; covering-PR matches stay deterministic, the rest may ask
the executor once) then re-runs `intake_issue` with `--require-ready` before
every `issue_to_pr`. **Serial by design:** default
`limits.max_issue_to_pr_per_pass` is **1** (ticket after ticket). K is an
optional pass budget, not concurrent worktrees/Pi/tmux.

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
approve + green checks + local tests → `pr_merge` + `close_issue` in one path; pending
**or transient GitHub 429/5xx while reading checks** → non-green waiting; confirmed
red → repair; secrets / `needs_human` / escalated `ai:needs-review` never merge.
Soft documentation nits must not route to `ai:needs-review`.
`pr_review` does not load `.lokay/approach.md` or ask the reviewer to compare
the diff to the builder plan. The plan stays builder evidence only.
Config: `merge.require_llm_review` (default true), `merge.require_checks` (default false).
Env: `LOKAY_REQUIRE_LLM_REVIEW`, `LOKAY_REQUIRE_CHECKS`, `LOKAY_MERGE_ENABLED`.

`resolve_conflicts` handles **merge conflicts**: `mergeable=CONFLICTING|DIRTY`
→ `lokay-pr-close` + re-label linked issue `ai:ready` so the next pass re-runs
`issue_to_pr` from current main (one stuck conflict must not freeze the mill).

- **conduction** edges = dependencies (Fala will not ready a node until upstream succeeded).
- **push** / **pr_merge** / **pr_create** also fail closed in the organ unless `test_local` conduction is ok (skip / `no_python_test_suite` counts). `pr_create` additionally requires a successful `push`. `push` / `pr_create` also require `assert_real_diff`: a diff that is only `.lokay/approach.md` / `.lokay/localize.json` is not progress and never opens a PR.
- **issue_to_pr red suite** does **not by itself** open a PR. One bounded AlphaCodium nest runs instead: `test_local` (first probe, records red so Fala can continue) → `repair_agent` (K=1 patch from the test log) → `test_local_recheck`. The recheck first runs the declared suite; if it is still red and the branch changes Python under `src/`, it may fall back to changed ticket tests plus conventional `tests/test_<changed-module>.py` tests. That changed scope must be green; an unknown or red ticket scope still fails closed. A green full or changed-scope recheck → push → pr_create. Recheck red / zero-diff / agent fail → path fails closed (`local_repair_exhausted`); the mill marks that seed stuck and takes the next one. There is no third repair attempt.
- **run_agent** is the only non-deterministic coding slot — external harness via `executor.command`/`args` (no vendor hardcode). See [`NO_STUBS.md`](NO_STUBS.md). For a seed classified separately as unbounded collection work, this slot receives a collector boundary: make only the bounded bootstrap patch; the deployed collector starts durably in the background after merge. Pi and the mill do not populate collection data or wait for completion.
- **plan_issue** is deterministic evidence before that coding slot.
- **localize** proposes paths immediately before the coding slot (serial path:
  `worktree_add → plan_issue → localize → run_agent`). Existing
  `.lokay/localize.json` paths skip the localize executor. Live mode may call the
  configured executor once for a JSON path list; Python validates and still
  fails closed on missing/empty localize — the coding agent does not start.
  `plan_issue.files_likely` is passed as `--extra-path`. Weak token hits do not
  pad the list to 40; a long list is a hint in the prompt, not a cage.
  A tests-only inferred list is a cage: matching `test_foo.py` promotes
  `foo.py`, and a still-empty product set opens first-party imports from
  those tests so the agent can edit product code.
  A skill / markdown hit is not product — `skills/influenzer-shorts` must
  not skip the import walk that opens `playbook.py`.
  Snake identifiers from the seed (`has_fair_hook`) are body needles in
  the whole file, not the first 8KiB.
  Standalone `X` is a platform stem (twitter/tweet), not a dropped
  one-letter token — otherwise #27 cages the agent in HN/brief.
- **run_agent timeout** (executor budget 1800s) is incomplete, not a graph hard-fail.
  The leftover tree is kept; `repair_agent` resumes the same corner / session
  once (K=1). Do not raise 1800 on the first shot.
  Re-view the issue first: if a sibling already closed it, skip with
  `reason=issue_closed` — do not continue or open a second PR.
  Harvest does not bury that reason (the ticket is already done) and
  clears a stale `no_pr` stuck row. `clear_issue` marks `cleared` so
  `save_stuck` cannot restore a delivered corpse. GitHub CLOSED on the
  mill repo (`mill_scope`) also drops leftover stuck rows after compact
  dropped the journal event. Harvest then drops stuck rows outside the
  mill catalog, including top-level Temida keys, so a mini mill cannot
  keep Temida/test corpses.
  `cycle_end` unlinks the start receipt after measuring. Harvest also
  drops leftover start-only cycle files outside mill catalog or GitHub-CLOSED.
- **Published-tip retry** (`origin/<branch>` exists — including a closed
  CONFLICTING tip that matches HEAD) resets the corner from `origin/<base>`
  and deletes the stale remote tip. KEEP only unpublished ahead that already
  contains `origin/<base>`, or a dirty leftover. Unpublished-but-behind-main
  (rebase_conflict leftover) also RESET — replaying those commits loops.
  Never force-push.
- **Miss harvest** (`factory_begin` → `harvest_fail_closed_children`): `plan_only`
  / `zero_diff` / `rebase_conflict` leave the slot after **3** unique `run_id`s;
  `push_failed` after **2**. A stale ledger row already `blocked` below that
  threshold is reconciled from the journal — harvest reopens the slot until
  unique-run N. At/above its reason's bound the miss row is terminal and is
  preserved verbatim: an old dead receipt cannot refresh its timestamp/error or
  re-enable it. Crash reasons (`local_repair_exhausted`, red recheck, bad ref)
  still block at 1 and stay buried. Harvest, dispatch, and reap do not CLOSE the issue. The repo
  mutex must not stay on one corpse.
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
