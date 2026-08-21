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
`localize` must not cage the agent in `tests/` when the seed only names a
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

1. **Survey** every managed repo: inbox, `work:ready` (with `ai:ready`), open `ai/fix/*` PRs
   (full newest-first page, cap 1000; hitting the cap is `survey_error`, not idle).
2. **Per-repo PR-first**: PR close-out (conflict / repair / triage / waiting) is
   scoped to each repository. An **actionable** AI PR in repo A does **not**
   freeze inbox triage or `issue_to_pr` in repo B. Manual/terminal PRs
   (`ai:needs-review`) never freeze unrelated repos. Issue-level
   `ai:needs-feedback` never freezes any repo. Safety: never open a second
   `ai/fix/*` PR in a repo that already has an open AI PR.
3. **Inbox triage + intake + optional split** (per repo, when that repo has no
   actionable open AI PR and its PR survey succeeded): undecided issues →
   triage rules, then **intake** → `CLOSE` | `READY` | `SPLIT` |
   rare `NEEDS_HUMAN`. Path: `issue_triage`
   (`get_issue → triage_issue → intake_issue → issue_split`). Hard facts
   (open/superseded/duplicate AI PR) stay deterministic. Semantic remainder is
   one structured executor call with the previous heuristic frame as fallback.
   Oversized / multi-epic / inventory blobs **auto-split**
   into bounded child issues (parent becomes `ai:tracker`, not `ai:ready`).
   A **bug** (`bug` / `kind:bug` / `[BUG]`) is one symptom, one fix: template
   Subsystem / Environment checkboxes (`##` or `**bold**`) are routing, not
   slices. Intake must not close the parent and mint empty children.
   Children re-enter inbox/intake on later passes. Fail closed: a failed PR
   survey for a repo refuses triage mutations **in that repo only**.
4. **PR close-out**: for open AI PRs — conflicts → close + re-ready; confirmed
   failed CI → `pr_repair`; pending **or transient GitHub/rate-limit checks** →
   wait non-green; mergeable + policy → `pr_triage` (LLM review → merge → close
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
   occupied, so a 29-repo catalog does not 429 the secondary budget
   before `select_implement`. Then `reap_stale_worktrees` drops leftover corners
   that cannot resume (merged, closed CONFLICTING, unpublished-behind-main)
   and KEEPs a live i2pr (from receipts **or** `working.json`), a repo
   whose PR survey failed, an open covering PR, or a dirty unpublished
   timeout leftover. A failed `list_prs` is unknown, not idle — wiping
   `prs_by_repo` must not let reap `push --delete` a published MERGEABLE
   tip (that closes the GitHub PR). A ready published
   tip is stale and is reaped; `issue_to_pr` RESETs from `origin/main`.
   Classify with one `ls-remote --heads` per repo — a per-branch fetch
   stalls the pass. Over-cap leftover stacks view at most four oldest
   issues; after a no-reap over_cap, skip those GitHub views for 300s without refreshing the stamp. The plan atom is trust-with-evidence,
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
restarts immediately; idle 0 waits the 60s StartInterval. Already 60s
crash KeepAlive skips python `plistlib`; missing plists stay missing. Delayed
`--install` double-forks out of the launchd process group so idle 0
cannot kill the reload. Same serial mill (K=1), same lock — not a
parallel fleet. Details:
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
  `host_ff → factory_begin → survey_prs → survey_inbox → survey_ready → plan_pass →
  dispatch_triage → resolve_conflicts → closeout_prs → reap_stale_implementing →
  refresh_occupancy → reap_stale_worktrees → select_implement →
  queue_conflict → dispatch_implement → compute_health → record_pass`.
  `factory_begin` fail-closes when in-cycle `host_ff` just fast-forwarded (`health=host_updated`)
  so a later launchd tick reinstalls and imports the new checkout. Launchd host-ff
  that already moved HEAD continues into uv reinstall + `lokay-daemon` in the same tick.
  Launchd does not `host_ff` while `mill.lock` is held; `LOKAY_PROCESS_HEAD`
  still refuses if HEAD moved under the already-imported daemon.
  After caretaker `lokay-host-ff`, mill-daemon sets `LOKAY_HOST_FF_FETCHED=1`
  so in-cycle `factory_pass` `host_ff` skips a second `git fetch origin/main`
  and preflight skips a second `git ls-remote origin HEAD`. Origin URL is
  still checked. Caretaker `lokay-host-ff` skips `git fetch origin/main` when
  GitHub `main` matches local `origin/main`. Probe failure or SHA mismatch
  still fetches. Standalone `lokay-daemon` still probes. Healthy first host
  check is not rerun (`gh api user` / ast.parse every lokay module). Repair
  still reruns `_check`.
  Fala inherit_env is a whitelist: every atom, including nested `recovery_mill`,
  must inherit `LOKAY_HOST_FF_FETCHED`. Missing key aborts the mill.
  Mill Fala sqlite under `~/.lokay/fala/daemon-cycle` and `factory` rotates
  when oversized (default 64 MiB) so idle ticks do not reopen a multi-GB
  journal. Product recovery stays on `state.jsonl`. Live `fala/i2pr/`
  journals stay.
  After each factory pass, leftover closeout parks leftover `work:ready` /
  `ai:ready` on GitHub-CLOSED mill issues. That is not a second hunt through
  every mill PR; GitHub CLOSED is enough. After an empty leftover, skip
  those GitHub lists for 300s so idle ticks do not pay them twice a minute.
  After a complete empty mill survey (no open AI PRs, inbox, or ready), skip
  those GitHub lists for 120s without refreshing the stamp. A live mill with
  that fresh stamp and an idle last-pass also skips hosting `factory_pass`
  (20 organ spawns) and the parent `daemon_cycle` Fala (6 recovery organs).
  When the stamp expires, the same idle mill cheap-probes those three GitHub
  lists. An empty probe refreshes the stamp and skips Fala; probe failure or
  remaining work hosts. Leftover closeout still runs after that skip via its
  own 300s TTL. Missing stamp, occupied last-pass, or pytest always hosts.
  mill-daemon skips caretaker `lokay-host-ff` when GitHub `main` already
  matches HEAD and `origin/main`. Fresh idle stamps skip the GitHub SHA
  probe. Busy lock still probes. Probe failure or SHA mismatch still runs
  host-ff. Local clones still run host-ff. Small mill / launchd logs skip
  python truncate. Small launchd stdio skips python inode reopen; fat logs
  still bound in place, then reopen. When last-pass is idle,
  it skips `lokay-daemon` (preflight + Fala) while empty-survey (120s) and
  leftover-closeout (300s) stamps are fresh. After leftover-stamp expiry, a
  cheap empty GitHub probe of CLOSED `work:ready` / `ai:ready` mill issues
  refreshes that stamp and still skips when the survey stamp is fresh.
  After survey-stamp expiry, a cheap empty GitHub probe of mill PR / inbox
  / ready lists refreshes the survey stamp. Probe failure, remaining
  leftovers, occupied last-pass, digest mismatch, or host-ff update still
  starts the daemon. Fresh idle skip with a persisted digest skips
  `checkout_digest` and `package_matches`. An `already_current` host-ff
  envelope skips python `host_ff_updated`. Fresh idle skip writes the
  launchd glance in bash and skips python `emit_launchd_glance` plus extra
  `bound_launchd_stdio`. Hosted ticks still scrape the mill log and bound
  launchd stdio around glance. Already under keep skips python
  `prune_mill_logs`. Fat mill-log dirs still prune. Probe skip, missing
  digest, host-ff update, or a hosted daemon still checks the wheel.
  After an empty leftover in-flight cache probe (`ai:in-progress` /
  `ai:pr-open` / `ai:ci-waiting` / `ai:repairing`), skip those GitHub lists
  for 300s without refreshing the stamp.
  After an empty leftover-ready probe (`ai:ready` without `work:ready`), skip
  that GitHub list for 300s without refreshing the stamp.
  After an empty leftover-incident probe (`<!-- lokay-preflight:… -->`), skip
  that GitHub list for 300s without refreshing the stamp. Probe failure does
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
