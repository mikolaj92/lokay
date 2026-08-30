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
  → recovery_mill (always: factory departments; leftover skip never starts repair)
```

The moving gate is one leaf. Repair is its own child graph. `recovery_mill`
is factory only — it does not classify, repair, or activate. Moving
forward is only a new PR or a merge on the last receipt. Leftover skip,
empty survey, and a stale receipt do not count as “not moving” and do not
start recovery. After one repair the graph always returns to the five
departments. The daemon owns only the singleton lock, health lease and initial
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
fails. It bounds the lock-owning `lokay-daemon` wait (default 180s) and
signals only that session so nested Fala cannot hold `mill.lock` past the
pass ceiling. Detached `issue_to_pr` sessions are not signalled. Inner
`compose_daemon_cycle` SIGALRM is not the lock release: native
`host_run_package` swallows it. The caretaker may write a small
`last-pass.json` with `health=pass_ceiling` when it kills the lock owner.
It does not idle-skip, host-ff, or rewrite the LaunchAgent plist
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
host_ff
  → factory_begin_host_gate          begin → factory_begin / departments
                                     restart → record_pass (host_updated, no product)
    → factory_begin                  (when gate route=begin)
  → select_self_repair_department → run_self_repair_department   (when last pass is a stall; skip idle / pass_ceiling / occupied — product wins)
  → select_issue_triage_department → run_issue_triage_department
  → select_executor_department → run_executor_department
  → select_pr_triage_department → run_pr_triage_department
  → select_pr_repair_department → run_pr_repair_department     (when sieve verdict is repair)
  → record_pass          → last-pass.json (new_pr | merge | none)
    → factory_pass_terminal
  → reap_stale_worktrees     → sibling child from factory_begin (leftover work copies)
```

| Atom | One job |
| --- | --- |
| `host_ff` | Mill host checkout: fetch + ff-only onto origin/main. Clean product branch returns to main. Never `reset --hard`. Fail-closed when dirty or diverged. |
| `factory_begin_host_gate` | Succeeds with `route=begin` or `route=restart`. Restart means host-ff moved HEAD under this process. Never `ok=false`: a failed gate still unblocks product children in Fala. |
| `factory_begin` | NODE child Fala of named LEAF agents: host-alive probe, catalog, pass workspace. `when` gate `route=begin`. Always writes `pass_dir` when the host probe routes `up`. No idle on these leaves. Empty surveys do not skip PRs or issues. Lease, fat preflight, harvest (`child_harvest`), and four terminals are off this path. |
| `select_self_repair_department` / `run_self_repair_department` | Department 1. Parent switch; run only on a confirmed stall (`did_not_move`). Same exclusions as `select_repair_route`: leftover skip, empty survey, occupied, idle, pass_ceiling, waiting. One pass is oil XOR product (product wins). Body is child Fala `self_repair_department`. Off never touches lokay main. |
| `select_issue_triage_department` / `run_issue_triage_department` | Department 2. Sieve only. Child Fala `issue_triage_department`: marks, split, intake. Zero `ai/fix`. Foreign assignee still skipped. |
| `select_executor_department` / `run_executor_department` | Department 3. Code and PR. Child Fala `executor_department`: a do issue becomes an open PR. No merge. Off = zero new `ai/fix`. |
| `select_pr_triage_department` / `run_pr_triage_department` | Department 4. PR sieve / merge. Child Fala `pr_triage_department`: list, checks, review, feedback, merge-commit. Verdict merge / feedback / repair. Does not start `pr_repair`. |
| `select_pr_repair_department` / `run_pr_repair_department` | Department 5. Existing `pr_repair` after a repair verdict from `run_pr_triage_department`. Conducts from the sieve run plus the PR-triage switch. Not started from inside `pr_triage_department`. Disabled skip leaves published feedback and does not touch the branch. |
| `reap_stale_worktrees` | sibling child `stale_worktree_reap`: collect → catalog → summarize. Conducts from `factory_begin` only. Throw / empty / `process.failed` / `adapter_failed` is a classified `route=failed` at the parent boundary, never a path abort. The factory_pass parent stays ok. Does not conduct departments or `record_pass`. Collect composes `protection` or `bound_slots`. Catalog composes `overflow_skip` or `apply_slot`. Summarize composes `skip_result` or `persist_result`. Overflow skips. KEEP live i2pr / occupancy / `pr_survey_failed` / open PR / dirty unpublished. Foreign leftover localize is REMOVE (`foreign_localize`) and beats live-i2pr / unpublished-or-dirty / uncommitted-real KEEP. |
| `record_pass` | write a small `last-pass.json` receipt: `outcome` is `new_pr` \| `merge` \| `none`. Conducts from `factory_begin` and the five department selects. Leftover overflow is a skip on the receipt, never a pass failure. Cleanup success is not required. |
| `factory_pass_terminal` | lift `record_pass.result` so `normalize_path_result` sees one authored tick. Does not wait on leftover work-copy cleanup. |
| mill Fala journals | every live `state.sqlite` under `~/.lokay/fala/<path>/` rotates at a 64 MiB ceiling; recovery stays on `state.jsonl`. Nested children never share the tree-root sqlite or overwrite a sibling sliced package. Over-cap is fail-closed if the file cannot be cut |
| leftover closeout | after each factory pass, one in-process catalog atom parks leftover `work:ready`/`ai:ready` on GitHub-CLOSED mill issues. No 30-slot unroll. Mill repo count never fail-closes prepare. Candidate overflow parks the first authored handful and leftover-skips the rest; it does not fail the pass. Do not paginate every mill PR to prove a closer. After an empty leftover, skip those GitHub lists for 300s. Fresh leftover skip does not require healthy. Fresh leftover-closeout skip is not applied. Leftover-closeout skip reports planned=not live. Leftover-closeout skip reports probe_failed. Hosted leftover parks still do. Unhealthy leftover-closeout still lists GitHub. Unhealthy leftover-closeout parks are planned. Hosted leftover-closeout reports applied. Empty leftover-closeout host is not applied. Leftover-closeout rate limit does not stamp empty. Pytest must not skip leftover GitHub lists using the mill stamp. |

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
`i2pr-delivery/`, and `coding-execution/`. `test_local_execution` is the same
class of nested child: per-issue under `test-local-execution/`. A shared
`local/test` journal lets one live pytest hold `no_declared_test` skip for
another repo, so PR triage never reaches `pr_merge`. Cache always runs and
returns `route=terminal|hit|miss`. A Fala `when` on a skipped cache atom fails
`run_declared_tests` (`condition_source_not_succeeded`), so inspect
`no_declared_test` is a succeeded cache `route=terminal` and pytest skips
because the route is not `miss`. Every other child path uses its own journal under
`~/.lokay/fala/<path_id>/`. Native Fala materializes one sliced
package next to that journal. Nested children must not overwrite
`~/.lokay/fala/lokay.fala-package.toml` or share `~/.lokay/fala/state.sqlite`.
Python `compose/*` may validate CLI contracts and
call `graph_run.run_path`; it must not re-implement fleet scheduling. Do not
grow `compose/*` with GitHub/git/agent logic beyond wiring. Hermes Kanban is not
the ledger for step order.

### `pr_triage_department` (PR sieve)

Two small blocks plus graph. List, checks, review, feedback, merge-commit.
Does not write product code. Does not call `pr_repair` from inside.

```text
list_pr_sieve
  → select_pr_sieve
    → run_pr_sieve                   when route=pr → child Fala pr_triage
      → select_pr_triage_verdict     merge / feedback / repair
        → summarize_pr_triage_department
```

A repair verdict is a value. The parent `pr_repair` department consumes it.

### `self_repair_department` (factory body)

Two small blocks. Parent `run_self_repair_department` invokes this child only
when the last receipt did not publish a new PR or merge. Leftover skip never
enters.

```text
open_self_repair_incident     LEAF  stall incident (did_not_move)
  → invoke_self_repair        LEAF  existing self_repair child; skipped without incident
```

Off: parent select routes skip and the mill goes straight to issue triage /
executor / PR triage. This graph never starts from leftover overflow.

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
   finishes, `recovery_mill` always runs the factory (five departments).
   Repair never loops as the mill. Activate is `self_repair_activate`.

It never creates a branch or PR. The coding agent can edit only the detached
worktree; deterministic atoms alone commit and push directly to `main`. The
`self_repair_run_agent` coding slot uses the same bounded 1800-second budget as
other agent paths. A successful path always returns `restart_required`; product
work never resumes in the stale daemon process.

### `issue_triage_department` (sieve + split + intake)

Two small blocks plus graph. Zero code. Zero PR. Parent
`run_issue_triage_department` invokes this child. Foreign assignees stay
skipped at `select_next_issue`.

```text
list_open_issues
  → run_issue_sieve_rows      nest issue_sieve_row until leftover empty
    → summarize_issue_triage_department   launched is always empty
```

`issue_sieve_row`:

```text
select_next_issue
  → issues_run_triage         when route=issue
    → select_issue_sieve      do / skip / park / human / split / intake
      → run_issue_sieve_split   when route=split   (children only)
      → run_issue_sieve_intake  when route=intake
        → summarize_issue_sieve_row
```

A "do" mark is not a branch. Executor is the next department. The catalog
loop is this child nest, not a daemon tick and not eight copied slots.
Leftover is consumed only on an authored skip (`needs_human`, `blocked`,
already-closed). `triage_not_done` / adapter fail keep the row.
`leftover=0` only when the takeable list is exhausted.

### `executor_department` (code and PR)

Two small blocks plus graph. Not issue sieve. Not PR sieve. Not merge.
Parent `run_executor_department` invokes this child whenever the switch is on.

```text
list_open_issues
  → run_executor_rows         nest executor_row until leftover empty or budget
    → summarize_executor_department   merged is always false
```

`executor_row`:

```text
select_next_issue
  → select_issue_do_row       ready leftover becomes do (no triage)
    → select_issue_executor   department switch
      → issues_launch_pr      when route=do → child Fala issue_to_pr
        → summarize_executor_row
```

`select_next_issue` only answers whether a takeable row remains. Empty
assignees, or only the configured mill, may be taken. Anyone else on the
assignee list is foreign and is skipped. `assign_issue` does not add the
mill beside them. A live `issue_to_pr` receipt occupies its repo: that repo
is not takeable. Leftover walks past it, same as a foreign assignee. A
failed launch because the receipt is still live consumes that repo from
leftover so the nest cannot spin the same ticket until the 180s pass
ceiling. Off: the launch when is never satisfied. Zero new `ai/fix`.
The parent still runs PR triage after executor; occupancy is queue
hygiene, not a scheduler and not a reason to skip merge.

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
        └─→ worktree_add          ready → plan / localize / coding
                                  missing → summarize (no product). Never ok=false:
                                  a failed worktree still unblocks localize in Fala.
              └─→ plan_issue   ← when worktree route=ready; grandchild Fala plan_issue_execution
                    └─→ localize     ← when worktree route=ready; grandchild Fala localize_execution.
                                       Never ok=false: empty/timeout is route=empty.
                          └─→ coding_execution  ← when localize route=ready; child Fala: run_agent + one JSON retry + one evidence round
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
has paths **for this issue** and every path exists in the worktree, skip the
localize executor and start `run_agent`. A leftover inherited from main
(other issue in `worktree`, missing issue id) is not a sieve. A same-issue
path list with a missing file or non-path token is also not a sieve —
discard and run deterministic + semantic localize. Live mode asks the
configured executor for a structured path proposal; Python still validates
against the tree. Extra/seed paths are kept only when they exist in the
worktree. A version token or vanished file is rejected. Empty after that
fails closed.
Invalid JSON / timeout falls back to the deterministic scorer. Not an
embedding service and not a second planner.

### `issue_triage` (triage child of `issue_triage_department`)

Child of `issue_triage_department`. Triage only: **robić / nie / oznaczyć / człowiek**.
Not implement. Triage must not close someone else's issue. Verdict `close`
parks (`apply_issue_mark`: `ai:blocked` + comment). `issue_split` is a later
child Fala, not an exit here.

```text
get_issue
  → resolve_issue_candidate
    → collect linked/covering PRs
      → resolve_issue_hard_facts
        ├─→ terminal triage (close / skip / blocked)
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
The executor department launches `issue_to_pr` only after a do mark.

### `pr_repair` (red checks on open ai/fix PR)

```text
pr_checks
  └─→ stage_repairing   ← no-op on labels: keep ai:ready
        └─→ worktree_add          ready → localize / run_agent
                                  missing → summarize (no product)
              └─→ localize    ← when worktree route=ready; paths from checks/review seed + tree. Never ok=false.
                    └─→ run_agent   ← when localize route=ready; repair prompt (only non-deterministic node)
                          └─→ commit_all
                                └─→ test_local   ← local pytest; skip if no suite
                                      └─→ assert_real_diff
                                            └─→ push   ← published tip; never rebase (force-push forbidden)
```

### `pr_triage` (sieve / merge policy → close issue)

```text
pr_checks
  └─→ classify_pr_triage_checks   ← wait | repair | review
        ├─ wait     → summarize (pending / offline; do not fail the pass)
        ├─ repair   → summarize repair verdict (red CI; no executor)
        └─ review   → collect evidence → publish verdict
              ├─ request_changes → summarize repair verdict
              ├─ secrets-human   → terminal
              └─ approve → worktree_add → test_local (record_red)
                    └─→ select_pr_triage_outcome
                          ├─ merge  → pr_merge → stage_clear → close_issue
                          └─ repair → summarize repair verdict (local suite red)
```

The parent `factory_pass` consumes that verdict and may invoke the
`pr_repair` department. With repair disabled, feedback remains published and no code
or branch mutation occurs. `pr_review` is fail-closed: invalid JSON,
`request_changes`, `needs_human`, or `secrets=true` never auto-merges.
Trusted auto-merge (`lokay.merge_policy`): with `merge.enabled` / `LOKAY_MERGE_ENABLED`,
approve + green checks + local tests → `pr_merge` + `close_issue` in one path; pending
**or transient GitHub 429/5xx while reading checks** → non-green waiting; confirmed
red CI or a recorded-red local suite → repair verdict for the parent; the parent may invoke the separate `pr_repair` NODE child;
secrets / `needs_human` / escalated `ai:needs-review` never merge.
A later `pr_triage` pass re-reviews the new SHA.
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
  `worktree_add` `route=ready` → `plan_issue` → `localize` → `coding_execution`). Existing
  `.lokay/localize.json` paths skip the localize executor only when they
  belong to this issue number. Live mode may call the
  configured executor once for a JSON path list; Python validates and still
  refuses an empty path list. Localize never `ok=false` (Fala unblocks
  children of failed). `route=ready` continues to coding; `route=empty`
  (timeout, invalid JSON, no paths) skips coding. Parent localize budget
  covers the child agents. Empty localize is not invalid-JSON retry.
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

Journal: `~/.lokay/fala/<path_id>/state.sqlite` (issue children under `i2pr/`, `i2pr-delivery/`, `issue-split/`, `coding-execution/`, `test-local-execution/`)  
Materialized package: `~/.lokay/fala/<path_id>/lokay.fala-package.toml`  
(`uv run --project <checkout>` filled in for every organ — never bare `python3`)
One `run_path` never rewrites the shared `~/.lokay/fala/lokay.fala-package.toml`.

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
