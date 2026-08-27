# Process graph (Fala)

**Order is the product.** Atomic `lokay-*` tools do one job each; Fala declares
which jobs run after which.

## Source of truth

[`fala/lokay.fala-package.toml`](../fala/lokay.fala-package.toml) — `src/lokay/data/lokay.fala-package.toml` is a packaged copy of `fala/` (byte-identical; CI fails if they drift).

### `daemon_cycle` (top-level parent)

```text
last_pass_moving
  → select_repair_route
    → recovery_incident (when last receipt did not move: no new PR and no merge)
      → recovery_run_self_repair (self_repair child Fala; skipped otherwise)
  → recovery_mill (always: factory PRs / issues; leftover skip never starts repair)
```

The moving gate is one leaf. Repair is its own child graph. `recovery_mill`
is factory only — it does not classify, repair, or activate. Moving
forward is only a new PR or a merge on the last receipt. Leftover skip,
empty survey, and a stale receipt do not count as “not moving” and do not
start recovery. After one repair the graph always returns to PRs /
issues. The daemon owns only the singleton lock, health lease and initial
carrier preflight. Fala owns product/recovery order. Every node above is a
separate Unix process returning one JSON envelope. A product run that
actually publishes or merges work records no systemic stall fingerprint.
Idle TTL lives in `factory_pass` as `classify_factory_idle`. Compose and the
LaunchAgent shell cannot decide that a tick does not run. A fresh empty-survey
stamp still hosts Fala and exits the authored idle route. Missing stamp hosts
the rest of the pass. Leftover closeout remains the authored
`leftover_closeout` path after a hosted product pass — not a bash skip.
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
stamp expires, the authored idle atom cheap-probes mill PR and open-issue
lists. An empty probe refreshes the stamp and exits idle inside Fala. Probe
failure or remaining work hosts the rest of `factory_pass`. Missing stamp,
occupied last-pass, or pytest always hosts. `scripts/lokay-mill-daemon.sh`
is OS only: lock, exec `lokay-daemon`, logs, bootstrap incident if exec
fails. It does not idle-skip, host-ff, or rewrite the LaunchAgent plist
on each tick. Plist `StartInterval=60` and crash KeepAlive
(`SuccessfulExit=false`) are host `--install` setup. Busy lock is an OS
lease and may skip exec. Host-ff runs only as the second `factory_pass`
atom after idle classify routes `host`.

Subprocess atoms pin `cwd` to the Lokay checkout (`PLACEHOLDER_PROJECT`). Fala's
durable host may chdir into `vendor/sqlite.fire` for dylib load; organs must not
inherit that cwd or they emit empty `adapter_failed` and starve the mill.

**Repair gate (two small processes):** `last_pass_moving` answers only
whether the last receipt published a new PR or merged. `select_repair_route`
composes that leaf with leftover skip (`leftover_overflow`, 200>30), empty
survey, stale / missing receipt, occupied / in-flight `issue_to_pr`, and
soft mill health (`waiting`, `repairing`, `idle`, `progress`, `offline`,
`overlap`). Those exclusions route `factory` and never start
`recovery_run_self_repair`. `recovery_incident` runs only when the last
receipt did not move; incidents reuse the preflight cooldown ledger
(`github.incident_cooldown_hours`). Activate stays a `self_repair_*` leaf.

### `factory_pass` (parent)

**Order lives in Fala.** Fleet scheduling is not a fat Python tick. The parent
path conducts one-job atoms; child workflow Falas are started from dispatch
atoms via `run_path`.

```text
factory_begin
  → prs                      → child Fala: list / select / triage-or-merge
    → issues                 → child Fala: list once, nest issue_row until idle or cap
      → record_pass          → last-pass.json (new_pr | merge | none)
        → factory_pass_terminal
  → reap_stale_worktrees     → sibling child from factory_begin (leftover work copies)
```

| Atom | One job |
| --- | --- |
| `factory_begin` | NODE child Fala of named LEAF agents: host-alive probe, catalog, pass workspace. Always writes `pass_dir` when the host probe routes `up`. No `when` / idle on these leaves. Empty surveys do not skip PRs or issues. Lease, fat preflight, harvest (`child_harvest`), and four terminals are off this path. |
| `prs` | child Fala: list open mill PRs, select one, review or merge. Conducts from `factory_begin`. Does not wait on leftover work-copy cleanup. |
| `issues` | child Fala: list open issues once, nest `issue_row` until leftover is empty or the implement budget is spent. Leftover consume only on authored skip; sito miss keeps the row. Ready leftover goes to issue-to-PR. Oil is not the product slot. Conducts from `factory_begin` and `prs`. Does not conduct from `reap_stale_worktrees`. A failed cleanup is not a gate. The parent does not unroll 1..8. |
| `reap_stale_worktrees` | sibling child `stale_worktree_reap`: collect → catalog → summarize. Conducts from `factory_begin` only. Throw / empty / `process.failed` / `adapter_failed` is a classified `route=failed` at the parent boundary, never a path abort. The factory_pass parent stays ok. Does not conduct `prs`, `issues`, or `record_pass`. Collect composes `protection` or `bound_slots`. Catalog composes `overflow_skip` or `apply_slot`. Summarize composes `skip_result` or `persist_result`. Overflow skips. KEEP live i2pr / occupancy / `pr_survey_failed` / open PR / dirty unpublished. Foreign leftover localize is REMOVE (`foreign_localize`) and beats live-i2pr / unpublished-or-dirty / uncommitted-real KEEP. |
| `record_pass` | write a small `last-pass.json` receipt: `outcome` is `new_pr` \| `merge` \| `none`. Conducts from `factory_begin`, `prs`, and `issues`. Leftover overflow is a skip on the receipt, never a pass failure. Cleanup success is not required. |
| `factory_pass_terminal` | lift `record_pass.result` so `normalize_path_result` sees one authored tick. Does not wait on leftover work-copy cleanup. |
| mill Fala journals | every live `state.sqlite` under `~/.lokay/fala/` (including the child journal at that root) rotates at a 64 MiB ceiling; recovery stays on `state.jsonl`. Over-cap is fail-closed if the file cannot be cut |
| leftover closeout | after each factory pass, one in-process catalog atom parks leftover `work:ready`/`ai:ready` on GitHub-CLOSED mill issues. No 30-slot unroll. Do not paginate every mill PR to prove a closer. After an empty leftover, skip those GitHub lists for 300s. Fresh leftover skip does not require healthy. Fresh leftover-closeout skip is not applied. Leftover-closeout skip reports planned=not live. Leftover-closeout skip reports probe_failed. Hosted leftover parks still do. Unhealthy leftover-closeout still lists GitHub. Unhealthy leftover-closeout parks are planned. Hosted leftover-closeout reports applied. Empty leftover-closeout host is not applied. Leftover-closeout rate limit does not stamp empty. Pytest must not skip leftover GitHub lists using the mill stamp. |

**Trust intentional issues:** fleet flow assumes issues from the repo owner /
configured assignee are purposeful. Do not invent new human-approval gates in
the pass spine. Intake `CLOSE` remains a sito verdict for clear obsolete /
wrong-shape / superseded cases only — it marks (`ai:blocked`), it does not
close GitHub. Never bias toward “distrust every ticket.” Goal:
human writes issue → mill delivers.

### `factory_begin` (child)

```text
probe_factory_host
  → load_factory_config
    → select_factory_scope
      → read_factory_stuck
        → create_factory_pass_dir
          → build_factory_begin_state
            → build_factory_working_state
              → seed_factory_occupancy
                → attach_factory_stuck
                  → persist_factory_begin_state
                    → persist_factory_working_state
                      → persist_factory_tick
```

NODE agent owns this graph. Each effector is a named LEAF agent (one
Unix process). `harvest_factory_children` already invokes child Fala
`child_harvest` — it is not a leaf on this path, so harvest skip cannot
eat the factory. No leaf has `when`. Empty surveys are not idle.

The mill invokes this parent path (`compose_factory_pass` → `run_path`).
`lokay-factory-tick` is the same parent Fala path — not a second in-process
mill. Parent journal: `~/.lokay/fala/factory/state.sqlite`. Issue-to-PR and
`coding_execution` children use per-issue journals under `i2pr/`,
`i2pr-delivery/`, and `coding-execution/`. Other child paths:
`~/.lokay/fala/state.sqlite`. Python `compose/*` may validate CLI contracts and
call `graph_run.run_path`; it must not re-implement fleet scheduling. Do not
grow `compose/*` with GitHub/git/agent logic beyond wiring. Hermes Kanban is not
the ledger for step order.

### `prs` (open PR review / repair / merge)

NODE for this child only. Four authored nodes. Not the `closeout_prs`
stamp catalog. Not leftover overflow. Do not implement `pr_triage` /
`pr_repair` internals here.

```text
list_open_prs              LEAF  live GitHub mill PRs (two small functions)
  → select_next_pr         LEAF  one PR
    ├─→ run_pr_triage_subflow   NODE slot → child Fala `pr_triage` (owns pr_repair)
    └─→ summarize_prs      LEAF  empty list skips the child and does not fail
```

Named child slot: `run_pr_triage_subflow` / `pr_triage`. A separate NODE
agent owns that subgraph. This path only launches it. One PR per pass.
Atom ids are unique.

### `self_repair` (emergency only)

```text
self_repair_prepare          child Fala: detached exact origin/main
  → self_repair_run_agent    leaf: coding slot in that worktree
    → self_repair_commit     leaf: commit_all
      → self_repair_validate child Fala: identity + suite + diff
        → self_repair_push_main   leaf: fast-forward only, exact unchanged base
          → self_repair_activate  child Fala: exact commit
            → self_repair_preflight  leaf: fresh process
              → self_repair_close    leaf: close the incident
```

Each `self_repair_*` step is its own leaf or child Fala. The moving-forward
gate (`last_pass_moving`) is a leaf outside this graph. Activate is not
inside `recovery_mill`. This path does not classify last-pass progress and
does not run the factory.

Entered only from:

1. **Daemon preflight lane** — Lokay unhealthy, minimal carrier healthy (not
   overlap / not carrier-down); or
2. **`daemon_cycle` last-pass gate** — `last_pass_moving` is one leaf (new
   PR or merge). `select_repair_route` composes leftover skip, empty
   survey, and a stale receipt so they never enter. After the child
   finishes, `recovery_mill` always runs the factory (PRs / issues).
   Repair never loops as the mill. Activate is `self_repair_activate`.

It never creates a branch or PR. The coding agent can edit only the detached
worktree; deterministic atoms alone commit and push directly to `main`. The
`self_repair_run_agent` coding slot uses the same bounded 1800-second budget as
other agent paths. A successful path always returns `restart_required`; product
work never resumes in the stale daemon process.

### `issues` (child: nest issue_row until idle)

Parent `factory_pass` invokes this child. Labels are not a gate.

```text
list_open_issues          LEAF  live GitHub open issues (once)
  → run_issue_rows        NODE  nest issue_row until leftover empty or budget spent
    → summarize_issues    LEAF  receipt leftover + leftover_issues (skip does not wipe)
```

The catalog loop is this child nest, not a daemon tick and not eight copied
slots. After an authored skip, `classify_issue_row` routes `continue` so the
next listed row is the next `issue_row`. Leftover is consumed only on an
authored skip (`needs_human`, `blocked`, already-closed). `triage_not_done` /
adapter fail / `sito_nie_robic` keep the row; a leftover row that is still
open and ready becomes `route=do` and goes to issue-to-PR in that pass. Lokay
oil is not the product slot while product leftover remains. `leftover=0` only
when the list is exhausted.

### `issue_row` (one catalog question, one issue_to_pr)

```text
select_next_issue         LEAF  is there a row? leftover walk, then one issue
  → issues_run_triage     NODE  when route=issue → child Fala issue_triage
    → select_issue_do     LEAF  do or skip; leftover consume only on authored skip
      → issues_launch_pr  NODE  when route=do → child Fala issue_to_pr
        → summarize_issue_row LEAF  one-row receipt
```

`select_next_issue` only answers whether a row remains. It does not hide the
loop. Parked / human-stop rows are already excluded by `list_ready_issues`.
Atom ids stay unique versus `triage_dispatch` / `implementation_dispatch`.

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
              └─→ plan_issue   ← grandchild Fala plan_issue_execution
                    └─→ localize     ← grandchild Fala localize_execution
                          └─→ coding_execution  ← child Fala: run_agent + one JSON retry + one evidence round
                                └─→ commit_all
                                      └─→ rebase_onto_base  ← fetch + rebase onto origin/main; conflict = fail closed
                                            └─→ test_local_execution   ← grandchild Fala; skip if no suite
                                            ├─ (red, recorded) → local_repair_execution   ← child Fala: K=1 patch + recheck
                                            ├─ (select_local_test skip) → miss repair; delivery still writes a route
                                            └─→ assert_real_diff ← refuse plan/localize-only diffs
                                                  └─→ push            ← only after green / honest skip
                                                        └─→ pr_create   ← grandchild Fala; only after successful push
                                                              └─→ stage_pr_open   ← no-op on labels: keep ai:ready
                                                                    └─→ list_prs
                                                                          └─→ pr_label
```

Delivery is not a god path. Grandchildren that already have their own Fala
(`plan_issue`, `localize`, `test_local_execution`, `pr_create`) stay separate
nodes. The two extracted nests are `coding_execution` and
`local_repair_execution`.

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
has paths **for this issue**, skip the localize executor and start `run_agent`.
A leftover inherited from main (other issue in `worktree`, missing issue id)
is not a sieve — discard and run deterministic + semantic localize. Live mode asks the
configured executor for a structured path proposal; Python still validates
against the tree, keeps extra/seed paths, and fails closed on an empty list.
Invalid JSON / timeout falls back to the deterministic scorer. Not an
embedding service and not a second planner.

### `issue_triage` (sito of parent `issues`)

Child of `issues`. Sito only: **robić / nie / oznaczyć / człowiek**.
Not implement. Sito must not close someone else's issue. Verdict `close`
parks (`apply_issue_mark`: `ai:blocked` + comment). `issue_split` is a later
child Fala, not an exit here.

```text
get_issue
  → resolve_issue_candidate
    → collect linked/covering PRs
      → resolve_issue_hard_facts
        ├─→ terminal sito (close / skip / blocked)
        └─→ issue_triage_agent → validate → one retry → one evidence round
              → finalize
                ├─→ apply_issue_ready     robić
                ├─→ apply_issue_skip      nie
                ├─→ apply_issue_blocked   nie (preflight incident leaf)
                ├─→ apply_issue_mark      zamknąć → park (no close_issue)
                └─→ apply_issue_manual    człowiek
```

Hard facts stay deterministic (still-open, superseded/merged PR, duplicate AI PR).
Semantic remainder is one structured executor call; invalid JSON gets one retry;
a second evidence request is człowiek. A close verdict marks; it does not close
GitHub. Own-work closeout after merge stays in `pr_triage` (`close_issue`).
Oversized / multi-epic work is człowiek until `issue_split` has its own agent.
Parent `issues` launches `issue_to_pr` only after robić.

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
  └─→ classify_pr_triage_checks   ← wait | repair | review
        ├─ wait     → summarize (pending / offline; do not fail the pass)
        ├─ repair   → pr_repair NODE child (red CI; do not inline)
        └─ review   → collect evidence → publish verdict
              ├─ request_changes / secrets-human → pr_repair NODE or terminal
              └─ approve → worktree_add → test_local (record_red)
                    └─→ select_pr_triage_outcome
                          ├─ merge  → pr_merge → stage_clear → close_issue
                          └─ repair → pr_repair NODE (local suite red)
```

`pr_review` is fail-closed: invalid JSON, `request_changes`, `needs_human`, or `secrets=true` never auto-merges.
Trusted auto-merge (`lokay.merge_policy`): with `merge.enabled` / `LOKAY_MERGE_ENABLED`,
approve + green checks + local tests → `pr_merge` + `close_issue` in one path; pending
**or transient GitHub 429/5xx while reading checks** → non-green waiting; confirmed
red CI or a recorded-red local suite → `pr_repair` NODE child (not inlined);
secrets / `needs_human` / escalated `ai:needs-review` never merge.
A later `prs` pass re-reviews the new SHA.
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
- **issue_to_pr red suite** does **not by itself** open a PR. The delivery
  parent records the first `test_local_execution` probe red, then invokes
  child Fala `local_repair_execution`: `repair_agent` (K=1 patch from the
  test log) → `test_local_recheck`. The recheck first runs the declared suite;
  if it is still red and the branch changes Python under `src/`, it may fall
  back to changed ticket tests plus conventional
  `tests/test_<changed-module>.py` tests. That changed scope must be green; an
  unknown or red ticket scope still fails closed. A green full or
  changed-scope recheck → push → pr_create. Recheck red / zero-diff / agent
  fail → path fails closed (`local_repair_exhausted`); the mill marks that
  seed stuck and takes the next one. There is no third repair attempt.
- **run_agent** is the only non-deterministic coding slot — external harness via `executor.command`/`args` (no vendor hardcode). See [`NO_STUBS.md`](NO_STUBS.md). For a seed classified separately as unbounded collection work, this slot receives a collector boundary: make only the bounded bootstrap patch; the deployed collector starts durably in the background after merge. Pi and the mill do not populate collection data or wait for completion.
- **plan_issue** is deterministic evidence before that coding slot.
- **localize** proposes paths immediately before the coding slot (serial path:
  `worktree_add → plan_issue → localize → coding_execution`). Existing
  `.lokay/localize.json` paths skip the localize executor only when they
  belong to this issue number. Live mode may call the
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
