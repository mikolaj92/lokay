# WORKING machine (Definition of Done)

**One Definition of Done.** An issue is done only when the designed change is
**quality code on `main`** — produced, reviewed by the mill's gates, and
**merged**. That is the only measure that the factory worked.

Not done: agent session `ok`, plan-only tree, open PR, closed-unmerged PR,
pass `health=progress`, green pytest, recovery plateau, or a spinning
machine that consumes tickets without landing them. Those are intermediate
signals. They may explain a miss. They never count as output.

Read-only semantic atoms (`intake`, `queue`, `localize`) report a `semantic`
object with `source=agent|fallback|bypass`, execution `status`, duration, and
isolated `session_kind`. `lokay-yield-report --config config.yaml --hours 24`
aggregates traces/failures from the existing compacted state JSONL and reads
merged PR / closed issue throughput from GitHub, the production source of truth. Before commit, one bounded
semantic relocalization may admit a necessary source/test neighbour outside the
initial scope; Python validates it and `assert_real_diff` remains the hard gate.

The coding slot must actually run. Default Pi argv uses `--session-id`
`{session}` so the first ticket *creates* the per-corner session and a
timeout retry resumes it — unless a sibling already closed the issue
(`reason=issue_closed`; do not continue or open a second PR).
`--session` looks up an existing file and exits
1 (`No session found matching 'lokay-…'`), which leaves only
`.lokay/approach.md` / `.lokay/localize.json` — a `plan_only` miss, not a PR.
Same-issue `.lokay/localize.json` is a sieve only when every path exists
in the worktree. Validate also drops extra/seed tokens that are not in the
tree. A version string or vanished file is not a cage: discard and
localize again. Empty localize (`route=empty`) skips `coding_execution`. It is not
`ok=false` and not an invalid-JSON coding retry. Parent localize timeout
covers the child agents. `localize` must not cage the agent in `tests/` when the seed only names a
test token (`gate` → `test_e2e_gates.py`): matching `test_foo.py` promotes
`foo.py`, and a still-empty product set opens first-party imports from those
tests. A tests-only scope is how #41/#26 go `plan_only`.
A skill / markdown hit is not product (`skills/influenzer-shorts` on #36
must still open `playbook.py` via the test imports). Snake identifiers
from the seed (`has_fair_hook`) are searched in the whole file.
Standalone `X` must stay a stem (twitter/tweet in product files); dropping
it is how #27 opens `brief_*`/`influenzer-hn` and never `playbook.py`.

The factory exists to turn designed issues into **good toys** — merged
product at the quality the gates already demand (real diff, tests that the
repo declared, no force-push junk). Fast broken toys are worthless. Machines
that only keep other machines busy — retries, receipts, health, self-repair —
are worthless if nothing lands. Quality without merge is a warehouse.
Merge without quality is scrap.

A miss (agent "succeeded" with no product, push refused, same ticket looping)
is a factory defect, not an honest wait. After bounded unique-run misses the
seed must leave the slot so the next designed issue can land. A stale
`stuck.json` row below its miss bound for `plan_only` / `zero_diff` /
`push_failed` is reconciled from the journal — harvest reopens the slot until
unique-run N. At/above its bound it is terminal and is not refreshed by a dead
receipt or old journal event. Crash / red-recheck rows stay buried. Tests and
pass health are not a representation of whether the mill works. Merges of
intended issues are.

Lokay is **working** only if it continuously mills its **delivery catalog**
**to that DoD**. Catalog is `repos.mikolaj92.yaml`; this host's mini mill
(`mill_scope`, `LOKAY_MILL_REPO`, default `mikolaj92/lokay`) delivers only
that one repo. Product mill for Temida and the rest is a host/CEO decision,
not an un-clamp on this machine. Order: survey →
**per-repo PR-first** (close-out) → inbox triage / implement in repos with no
open AI PR. Agent must be **real** ([`NO_STUBS.md`](NO_STUBS.md)). Minimize
human: humans write issues; the mill consumes them to merged results — do not
add new human gates.

For the autonomous mill Definition of Working (pass promises, night profile,
hermetic canaries, how to read `lokay status` / `last-pass.json`), see
[`AUTONOMY.md`](AUTONOMY.md).

## Issue ledger = chat with the mill

Operators should read **GitHub Issues** for *decisions* (`ai:ready` / blocked /
feedback / frozen / tracker) and **open PRs + live jobs** for in-flight work.
In-flight is not an issue label. `ai:ready` stays until merge + `stage_clear` +
close. Parking / residual unchanged: `ai:blocked`, `ai:needs-feedback`,
`ai:needs-review`, `ai:tracker`. Diagram:
[`AUTONOMY.md`](AUTONOMY.md#issue-ledger--chat-with-the-mill).

## Product law: minimize human in the loop

**Humans author intentional issues; the mill consumes.** Trust the issue author:
when the issue is created or owned by the trusted operator (`github.assignee`,
default mikolaj92), assume it makes sense — prefer **READY+implement** autonomy.
Do not add distrustful human gates or clarification parking for ordinary
operator-authored work. Deeper skepticism is for foreign/external authors if
distinguished at all.

**Soul is operator-set.** What Lokay *is* — Fala graph, serial mill, one DoD
(quality code on `main`) — is decided here, not in the inbox. Others may file
that it **hangs** or **does not work as described**. They may not file against
the quintessence / soul / product law. Those issues CLOSE (`foreign_essence_objection`).
Operational reports stay and get milled.

The system should **CLOSE**, **SPLIT**, or **READY+implement**. Maximize
autonomy. `NEEDS_HUMAN` / `ai:needs-feedback` is a **rare residual** after
deterministic rules fail closed — never the default escape hatch for oversized
or ambiguous work that can be auto-split.

`lokay status --human` lists that residual mailbox across managed repos. It is
**exception reporting**, not a workflow step. The mill does **not** wait on a
human digest and does **not** freeze other repos because one issue is parked
`ai:needs-feedback` or a PR is `ai:needs-review`.

Light glance metrics from `last-pass.json` (ready / PR / mergeable / progress)
and the read-only `lokay-yield-report` are fine observability — not a metrics
product. Green repository verification may be reused only for the identical
`HEAD`, `origin/main`, and declared test command. See [`AUTONOMY.md`](AUTONOMY.md).

## Full pass (one tick)

1. **Survey** every managed repo: inbox, open catalog issues (human stops exclude; mill labels are not a gate), open `ai/fix/*` PRs
   (full newest-first page, cap 1000; hitting the cap is `survey_error`, not idle).
2. **Per-repo PR-first**: PR close-out (conflict / repair / triage / waiting) is
   scoped to each repository. An **actionable** AI PR in repo A does **not**
   freeze inbox triage or `issue_to_pr` in repo B. Manual/terminal PRs
   (`ai:needs-review`) never freeze unrelated repos. Issue-level
   `ai:needs-feedback` never freezes any repo. Safety: never open a second
   `ai/fix/*` PR in a repo that already has an open AI PR.
3. **Inbox sito** (per repo, when that repo has no
   actionable open AI PR and its PR survey succeeded): undecided issues →
   `issue_triage` sito: robić / nie / oznaczyć / człowiek. Not implement.
   Sito may mark; it must not close someone else's issue.
   Hard facts (open/superseded/duplicate AI PR) stay deterministic. Semantic
   remainder is one structured executor call. Oversized / multi-epic work is
   człowiek until the later `issue_split` child. A **bug**
   (`bug` / `kind:bug` / `[BUG]`) is one symptom, one fix. Fail closed: a failed
   PR survey for a repo refuses triage mutations **in that repo only**.
4. **PR close-out**: for open AI PRs — conflicts → close + re-ready; confirmed
   failed CI → `pr_repair`; pending **or transient GitHub/rate-limit checks** →
   wait non-green; mergeable + policy → `pr_triage` (LLM review → merge → close
   issue). Land code in a repo before opening a new front there.
   - Same head SHA: do not re-post / re-run LLM review (`already_reviewed_head`).
   - `request_changes` may auto-repair a few times (`limits.max_request_changes_per_pr`,
     default 2); then escalate to `ai:needs-review` (manual terminal).
   - `ai:request-changes` alone is **not** a terminal label; only `ai:needs-review` is.
5. **Implement open catalog work (serial by design)**: unlabeled inbox is
   work — `work:ready` is not a gate. One ticket after another. `K` /
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
   configured executor → commit → **`rebase_onto_base`** (fail closed on
   conflict; never force-push) → tests → push → PR. A retry on a
   deterministic `ai/fix/*` branch RESETs when `origin/<branch>` still
   exists (closed CONFLICTING tip) **or** the unpublished leftover is
   behind `origin/main` (rebase_conflict replay). KEEP only unpublished
   ahead that already contains main, or a dirty leftover. `pr_repair`
   does **not** rebase a published tip.
   After closeout,
   `refresh_occupancy` marks just-merged / still-coding repos occupied
   and re-lists PRs only on leftover-ready repos that are not already
   occupied, so a 29-repo catalog does not 429 the secondary budget.
   Occupancy refresh, surveys, closeout, and stale reaps stay in the
   path as housecleaning for passes with no selected work — they are
   not the gate to `select_implement`. Select conducts from
   `factory_begin` (pass workspace + configured catalog).
   `queue_conflict` / `dispatch_implement` take a visible
   `when select_implement.route == selected`. Hygiene nodes take
   `when select_implement.route == none` and do not run in a selected
   pass, so their 1800–7200s budgets cannot consume the 180s pass
   ceiling before `dispatch_implement` or the receipt.
   `compute_health` / `record_pass` conduct from dispatch, not from
   the worktree reap. It drops leftover corners
   that cannot resume (merged, closed CONFLICTING, unpublished-behind-main).
   `uv.lock`-only is not real uncommitted content, so a CLOSED leftover with
   only a dirty lockfile can archive. KEEP a live i2pr (from receipts **or**
   `working.json`), a repo whose PR survey failed, an open covering PR, or a
   dirty unpublished timeout leftover. A failed `list_prs` is unknown, not idle — wiping
   `prs_by_repo` must not let reap `push --delete` a published MERGEABLE
   tip (that closes the GitHub PR). A ready published
   tip is stale and is reaped; `issue_to_pr` RESETs from `origin/main`.
   Classify with one `ls-remote --heads` per repo — a per-branch fetch
   stalls the pass. Over-cap leftover stacks view at most four oldest
   issues; after a no-reap over_cap, skip those GitHub views for 300s without refreshing the stamp. Pytest must not skip over-cap GitHub views using the mill stamp. The plan atom is trust-with-evidence,
   not a human gate. `pr_review` is blind to `.lokay/approach.md`
   (ticket + code diff + tests only). For a seed classified separately as unbounded collection
   work, the executor may make only the bounded collector/bootstrap patch: the
   deployed collector starts durably in the background after merge. Pi and the
   mill never populate its data or wait for it to finish; a later issue observes
   whether it is accruing. Stuck → ledger → `ai:blocked`. Live ready with
   `executor.enabled: false` is a **stall**.
6. **Health** (honest):
   - `idle` — survey finds no remaining work
   - `progress` — mutations moved the queue this pass
   - `repairing` — active repair / request_changes cycle (not mill-failing)
   - `waiting` — pending CI, no-CI while `require_checks`, review limbo,
     green PRs while `merge.enabled` false (`remaining.merge_disabled`),
     only manual PRs (same soft matrix as `merge_policy`), or ready
     tickets frozen by per-repo PR-first / occupancy
   - `stall` — actionable work with no progress (true stuck / agent disabled;
     not merge-disarmed green; not ready behind an open AI PR or live job)
   - `survey_error` — list atoms failed (refuse false idle)

## Continuous mill

LaunchAgent (cron heartbeat) **and** optional GitHub event wake. Cron keeps
the mill turning; event wake (`lokay-wake` on a self-hosted `lokay-mill`
runner) reacts when an issue opens / is labeled `ai:ready` or when PR checks
complete. KeepAlive is crash-only (`SuccessfulExit=false`): a failed tick
restarts immediately; idle 0 waits the 60s StartInterval. Plist
`StartInterval=60` and crash KeepAlive are host `--install` setup
(`plutil`, not a per-tick rewrite). Missing plists stay missing. The
LaunchAgent shell leases `mill.lock` and execs `lokay-daemon`; idle TTL
and host-ff live in `factory_pass` (`host_ff` then `factory_begin_host_gate` begin|restart, then begin only on begin). Same serial mill (K=1), same lock —
not a parallel fleet. Details:
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
   minimal carrier remains healthy (not overlap, not carrier-down). A
   transient GitHub 503 on `/user` is not a missing token. Or
2. **Last-pass gate** — `last_pass_moving` is one leaf (new PR or merge
   only). `select_repair_route` composes leftover skip / empty survey /
   stale receipt so they never start repair. Only then does `daemon_cycle`
   file one deduplicated incident and enter the `self_repair` child Fala.
   `recovery_mill` hosts one `factory_pass`; activate stays `self_repair_activate`.

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
  `factory_begin` plus five departments (`self_repair`, `issue_triage`,
  `executor`, `pr_triage`, `pr_repair`) then `record_pass` →
  `factory_pass_terminal`.
  `reap_stale_worktrees` is a sibling child from `factory_begin`. Failed
  leftover-work-copy cleanup is a classified route, not `process.failed`;
  departments and `record_pass` do not wait on it.
  One pass is oil XOR product (product wins). Last-pass receipt includes
  `lane: product | oil | idle`. The self_repair department skips on idle,
  pass_ceiling, occupied, leftover skip, and empty survey; only a stall
  (`did_not_move`) starts oil.
  `factory_begin` opens a pass workspace after a short host-alive probe.
  Empty survey snapshots do not idle or skip PRs and issues. Launchd does not exec
  `lokay-daemon` while `mill.lock` is held; `LOKAY_PROCESS_HEAD`
  still refuses if HEAD moved under the already-imported daemon.
  Host-ff lives only in Fala. The mill-daemon shell is OS only (lock, exec,
  logs, bootstrap incident, 180s lock-owner ceiling). Nested Fala SIGALRM
  does not release `mill.lock`. Detached `issue_to_pr` survives the ceiling.
  Standalone `lokay-daemon` still probes. Healthy first host
  check is not rerun (`gh api user` / ast.parse every lokay module). Repair
  still reruns `_check`.
  Fala inherit_env is a whitelist: every atom, including nested `recovery_mill`,
  must inherit `LOKAY_HOST_FF_FETCHED`. Missing key aborts the mill.
  Every live Fala sqlite under `~/.lokay/fala/<path>/` is maintained through
  `fala.maintain_journal` when oversized (default 64 MiB) so idle ticks do
  not reopen a multi-GB journal. Heartbeat journals also finalize and delete
  `created` leftovers left by a 180s SIGKILL, through `finalize_run` then
  `delete_terminal_run`. Detached issue-to-PR journals are not finalized. Nested children never share the tree-root
  sqlite or overwrite a sibling materialized package. The journal is a pass
  trace, not world history. Product recovery stays on `state.jsonl`.
  Over-cap is fail-closed if Fala cannot maintain the file.
  After each factory pass, leftover closeout parks leftover `work:ready` /
  `ai:ready` on GitHub-CLOSED mill issues. That is not a second hunt through
  every mill PR; GitHub CLOSED is enough. Mill repo count never fail-closes
  prepare. Candidate overflow parks the first authored handful and leftover-
  skips the rest; it does not fail the pass. After an empty leftover, skip
  those GitHub lists for 300s so idle ticks do not pay them twice a minute.
  Fresh leftover skip does not require healthy. Fresh leftover-closeout
  skip is not applied. Leftover-closeout skip reports planned=not live.
  Leftover-closeout skip reports probe_failed.
  Hosted leftover parks still do.
  Unhealthy leftover-closeout still lists GitHub.
  Unhealthy leftover-closeout parks are planned.
  Hosted leftover-closeout reports applied.
  Empty leftover-closeout host is not applied.
  Leftover-closeout rate limit does not stamp empty.
  Pytest must not skip leftover GitHub lists using the mill stamp.
  After a complete empty mill survey (no open AI PRs, inbox, or ready), skip
  those GitHub lists for 120s without refreshing the stamp.
  Inbox rate limit does not stamp empty. A live mill with
  that fresh stamp and an idle last-pass still hosts `factory_pass`;
  `classify_factory_idle` exits authored idle. Missing stamp, occupied
  last-pass, or pytest always hosts the rest of the pass. When the stamp
  expires, the same idle mill cheap-probes those three GitHub lists inside
  Fala. An empty probe refreshes the stamp and idles; probe failure or
  remaining work hosts. Leftover closeout is the authored `leftover_closeout`
  path after a hosted product pass. Idle CLASSIFY_CAP skips no-issue leftovers so
  Fala cannot starve mill issues. Idle CLASSIFY_CAP skips dirty-real leftovers
  so KEEP cannot starve mill issues. Harvest leftovers are not mill issues.
  Idle CLASSIFY_CAP reaps empty no-issue leftovers so harvest leftovers
  cannot freeze mill porcelain. Idle KEEP-only leftovers still write the
  over-cap stamp. Idle worktree removal requires healthy. Classification and
  KEEP stamping do not. Hosted worktree removal also requires healthy; hosted
  KEEP classification does not. Idle over-cap skip outlives leftover-probe.
  Nested clones are not mill leftover
  worktrees. Mill worktrees keep a .git file. Pytest must not skip GitHub surveys
  using the mill stamp.
  Leftover closeout stays the authored `leftover_closeout` path after a
  hosted product pass. The LaunchAgent shell does not leftover-probe or
  idle-skip. Host-ff and cheap mill-list probes run only inside Fala.
  After an empty leftover in-flight cache probe (`ai:in-progress` /
  `ai:pr-open` / `ai:ci-waiting` / `ai:repairing`), skip those GitHub lists
  for 300s without refreshing the stamp.
  Fresh leftover-cache skip does not require healthy. Fresh leftover-cache
  skip is not applied. Leftover-cache skip reports probe_failed.
  Hosted leftover-cache parks do.
  Unhealthy leftover-cache parks do not clear the stamp. Unhealthy leftover-cache parks are planned.
  Leftover-cache reaped_count excludes planned parks.
  Hosted leftover-cache reports applied.
  Leftover-cache rate limit does not stamp empty.
  Idle leftover-cache skip outlives leftover-probe. Hosted factory_pass
  stays at 300s.
  Idle daemon_cycle skip still runs leftover-cache.
  Pytest must not skip leftover-cache GitHub lists using the mill stamp.
  After an empty leftover-ready probe (`ai:ready` without `work:ready`), skip
  that GitHub list for 300s without refreshing the stamp.
  Fresh leftover-ready skip does not require healthy. Fresh leftover-ready
  skip is not applied. Leftover-ready skip reports probe_failed.
  Hosted leftover-ready parks still do.
  Unhealthy leftover-ready still lists GitHub.
  Unhealthy leftover-ready parks are planned.
  Empty leftover-ready host is not applied.
  Leftover-ready rate limit does not stamp empty.
  Idle leftover-ready skip outlives leftover-probe. Hosted factory_pass
  stays at 300s.
  Idle daemon_cycle skip still runs leftover-ready.
  Pytest must not skip leftover-ready GitHub lists using the mill stamp.
  After an empty leftover-incident probe (`<!-- lokay-preflight:… -->`), skip
  that GitHub list for 300s without refreshing the stamp.
  Fresh leftover-incident skip is not applied.
  Leftover-incident skip reports planned=not live.
  Empty leftover-incident host is not applied.
  Empty leftover-incident host reports planned=not live.
  Leftover-incident probe failure reports probe_failed.
  Leftover-incident probe failure reports planned=not live.
  Leftover-incident ImportError is not applied.
  Leftover-incident ImportError reports planned=not live.
  Leftover-incident empty name is not applied.
  Leftover-incident empty name reports planned=not live.
  Leftover-incident OSError is not applied.
  Leftover-incident OSError reports planned=not live.
  Leftover-incident host reports probe_failed.
  Leftover-incident skip reports probe_failed.
  Leftover-incident ImportError reports probe_failed.
  Leftover-incident empty name reports probe_failed.
  Leftover-incident OSError reports probe_failed.
  Idle leftover-incident skip outlives leftover-probe. Hosted factory_pass
  stays at 300s.
  Pytest must not skip leftover-incident GitHub lists using the mill stamp.
  Probe failure does
  not write the stamp. Opening a new incident clears it.
  Dispatch atoms start the smaller workflow Falas through a separate journal
  boundary.
  `compose/tick.py` is a thin in-process bridge for `lokay-tick` / autonomy
  canaries — not the multi-repo brain.
- `pr_review`: structured LLM gate before auto-merge when `merge.require_llm_review`.
  Comments carry a durable `<!-- lokay-review head=… -->` marker for idempotency.
- Env knobs (see `config.example.yaml`): `LOKAY_MERGE_ENABLED`, `LOKAY_REQUIRE_CHECKS`,
  `LOKAY_REQUIRE_LLM_REVIEW`. Keep `merge.enabled: false` in dry-run configs; enable
  merge on the live mill via env.
