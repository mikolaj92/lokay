# WORKING machine (Definition of Done)

**One Definition of Done.** An issue is done only when the designed change is
**quality code on `main`** — produced, reviewed by the lokay's gates, and
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
receipt or old journal event. Verify / no_pr / local-repair fail-closed rows
use a local cooldown with auto-clear — never eternal stuck limbo against OPEN
ready (CEO: ready|split|skip|close+reason). Tests and
pass health are not a representation of whether the lokay works. Merges of
intended issues are.

Lokay is **working** only if it continuously lokays its **delivery catalog**
**to that DoD**. Catalog is `repos.mikolaj92.yaml`; this host's mini lokay
(`factory_scope`, `LOKAY_REPO_SCOPE`, default `mikolaj92/lokay`) delivers only
that one repo. Product lokay for Temida and the rest is a host/CEO decision,
not an un-clamp on this machine. Order: survey →
**per-repo PR-first** (close-out) → inbox triage / implement in repos with no
open AI PR. Agent must be **real** ([`NO_STUBS.md`](NO_STUBS.md)). Minimize
human: humans write issues; the lokay consumes them to merged results — do not
add new human gates.

For the autonomous lokay Definition of Working (pass promises, night profile,
hermetic canaries, how to read `lokay status` / `last-pass.json`), see
[`AUTONOMY.md`](AUTONOMY.md).

## Issue ledger = chat with the lokay

Operators should read **GitHub Issues** for *decisions* (`ai:ready` / blocked /
feedback / frozen / tracker) and **open PRs + live jobs** for in-flight work.
In-flight is not an issue label. `ai:ready` stays until merge + `stage_clear` +
close. Parking / residual unchanged: `ai:blocked`, `ai:needs-feedback`,
`ai:needs-review`, `ai:tracker`. Diagram:
[`AUTONOMY.md`](AUTONOMY.md#issue-ledger--chat-with-the-lokay).

## Product law: minimize human in the loop

**Humans author intentional issues; the lokay consumes.** Trust the issue author:
when the issue is created or owned by the trusted operator (`github.assignee`,
default mikolaj92), assume it makes sense — prefer **READY+implement** autonomy.
Do not add distrustful human gates or clarification parking for ordinary
operator-authored work. Deeper skepticism is for foreign/external authors if
distinguished at all.

**Soul is operator-set.** What Lokay *is* — Fala graph, serial lokay, one DoD
(quality code on `main`) — is decided here, not in the inbox. Others may file
that it **hangs** or **does not work as described**. They may not file against
the quintessence / soul / product law. Those issues CLOSE (`foreign_essence_objection`).
Operational reports stay and get lokayed.

The system should **CLOSE**, **SPLIT**, or **READY+implement**. Maximize
autonomy. `NEEDS_HUMAN` / `ai:needs-feedback` is a **rare residual** after
deterministic rules fail closed — never the default escape hatch for oversized
or ambiguous work that can be auto-split.

`lokay status --human` lists that residual mailbox across managed repos. It is
**exception reporting**, not a workflow step. The lokay does **not** wait on a
human digest and does **not** freeze other repos because one issue is parked
`ai:needs-feedback` or a PR is `ai:needs-review`.

Light glance metrics from `last-pass.json` (ready / PR / mergeable / progress)
and the read-only `lokay-yield-report` are fine observability — not a metrics
product. Green repository verification may be reused only for the identical
`HEAD`, `origin/main`, and declared test command. See [`AUTONOMY.md`](AUTONOMY.md).

## Full pass (one tick)

The parent is authored `factory_pass`. Order lives in the Fala package, not in this prose.

1. **Harvest** child journals (`harvest_factory_children`), then **host-ff**: fetch + ff-only onto origin/main. Never `reset --hard`. Fail-closed when dirty or diverged.
2. **Host gate** (`factory_begin_host_gate`): `route=begin` opens the workspace; `route=restart` means host-ff moved HEAD under this process and the pass records a receipt without product work; `route=blocked` / `health=host_behind` is a failed or missing host sync, not a restart. The gate stays `ok=true` so Fala can still reach the receipt.
3. **`factory_begin`** (only on `begin`): host-alive probe, catalog, pass workspace. Empty surveys do not skip PRs or issues.
4. **Five departments**, in authored order. Each is a switch plus a child Fala. One pass is self XOR product (product wins).
   - `self_repair` — only a confirmed stall (`did_not_move`). Idle, waiting, occupied, leftover skip, empty survey and pass ceiling do not start it.
   - `issue_triage` — sieve only: ready → implement, split, skip (no stamp), or close with a reason. Never stamp `ai:frozen` / `ai:needs-feedback` / `ai:blocked`.
   - `executor` — one do-issue becomes an open PR. No merge. `K` / `limits.max_issue_to_pr_per_pass` (default **1**) is a pass budget, not concurrent worktrees. At most one attempt / one open AI PR per repo. Before coding, `lokay-queue-conflict` demotes clear contradictions, then the authored `intake_check_execution` path (`lokay-intake-check`) so a ready issue without intake cannot implement. Inside delivery: worktree from `origin/main` → `plan_issue` → configured executor → commit → `rebase_onto_base` (fail closed on conflict; never force-push) → tests → push → PR.
   - `pr_triage` — list, checks, review, feedback, merge-commit. Verdict merge / feedback / repair. Does not start repair itself.
   - `pr_repair` — only after a repair verdict from triage, inside the per-PR lifetime budget. A merged or closed target is a fail-closed skip.
5. **`record_pass`** then **`factory_pass_terminal`**: receipt `outcome` is `new_pr` | `merge` | `none`. A detached worker start is occupancy, not a new PR.
6. **`reap_stale_worktrees`** is a sibling from `factory_begin_host_gate` and `factory_begin`. It does not gate the departments or the receipt. KEEP live issue-to-PR, a failed PR survey, an open covering PR, or a dirty unpublished leftover. Foreign leftover localize is REMOVE.

Quality that stays, regardless of geometry:

- `K=1` is the recommended default. `K>1` is rare breadth across already-isolated clean repos, not concurrent workers in one repo.
- Rebase onto base fails closed. Never force-push.
- Same head SHA is not reviewed twice (`already_reviewed_head`).
- `request_changes` may auto-repair a few times (`limits.max_request_changes_per_pr`, default 2); then escalate to `ai:needs-review`.
- A failed PR survey refuses triage mutations in that repo only. It does not freeze other repos.
- An actionable AI PR in repo A does not freeze triage or delivery in repo B. Never open a second `ai/fix/*` PR in a repo that already has one.

**Health** (honest):

- `idle` — survey finds no remaining work
- `progress` — mutations moved the queue this pass
- `repairing` — active repair / request_changes cycle (not lokay-failing)
- `waiting` — pending CI, no-CI while `require_checks`, review limbo, green PRs while `merge.enabled` is false, only manual PRs, or ready tickets frozen by per-repo occupancy
- `stall` — actionable work with no progress (true stuck / agent disabled)
- `survey_error` — list atoms failed (refuse false idle)

## Continuous lokay

LaunchAgent (cron heartbeat) is the clock. There is no GitHub Actions wake
and no self-hosted Actions runner. `lokay-wake` is a local operator command
that routes one issue or PR into triage or a bounded factory pass; nothing in
`.github/workflows` calls it. KeepAlive is crash-only (`SuccessfulExit=false`): a failed tick
restarts immediately; idle 0 waits the 60s StartInterval. Classified
`preflight_failed` is a gate and must exit 0 so the interval applies. Plist
`StartInterval=60` and crash KeepAlive are host `--install` setup
(`plutil`, not a per-tick rewrite). Missing plists stay missing. The
LaunchAgent shell leases `lokay.lock` and execs `lokay-daemon`;
host-ff lives in `factory_pass` (`harvest_factory_children`, then `host_ff`, then `factory_begin_host_gate` begin|restart|blocked, then begin only on begin). Same serial lokay (K=1), same lock —
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
uv run lokay-work --config config.yaml --live --max-passes 8
```

Merge policy (fail closed): with `merge.enabled` / `LOKAY_MERGE_ENABLED`, the lokay
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
[`HEALTH.md`](HEALTH.md).

**ok=false** when work remains but lokay is not live-ready → NOT WORKING.
`repairing` / `waiting` are ok (honest wait), not recovery thrash.
`--human` does not set lokay not-working; it only lists residuals.

## Self-repair / recovery (narrow)

Self-repair must **not** steal cycles from normal review limbo or per-repo waiting.
Product lokay time wins over emergency recovery.

**Self-repair may run only when:**

1. **Preflight lane** — daemon preflight proves Lokay unhealthy while the
   minimal carrier remains healthy (not overlap, not carrier-down). A
   transient GitHub 503 on `/user` is not a missing token. Or
2. **Last-pass gate** — `last_pass_moving` is one leaf (new PR or merge
   only). `select_repair_route` composes leftover skip / empty survey /
   stale receipt so they never start repair. Only then does `daemon_cycle`
   file one deduplicated incident and enter the `self_repair` child Fala.
   `recovery_factory` hosts one `factory_pass`; activate stays `self_repair_activate`.

**Never mint a systemic stall fingerprint / never fill the 4-of-5 quorum for:**

- lokay `health=waiting` (pending CI, merge-disarmed green, review limbo, only
  manual/`ai:needs-review` PRs)
- lokay `health=repairing` (active repair / request_changes cycle)
- other honest soft outcomes (`idle`, `progress`, `offline`, `overlap`)
- per-event `pr_repair` / `issue_to_pr` / `pr_triage` failures while the lokay
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

- `factory_pass` is the parent Fala run used by the lokay. It conducts
  `factory_begin` plus five departments (`self_repair`, `issue_triage`,
  `executor`, `pr_triage`, `pr_repair`) then `record_pass` →
  `factory_pass_terminal`.
  `reap_stale_worktrees` is a sibling child from `factory_begin`. Failed
  leftover-work-copy cleanup is a classified route, not `process.failed`;
  departments and `record_pass` do not wait on it.
  One pass is self XOR product (product wins). Last-pass receipt includes
  `lane: product | self | idle`. The self_repair department skips on idle,
  pass_ceiling, occupied, leftover skip, and empty survey; only a stall
  (`did_not_move`) starts self_repair.
  `factory_begin` opens a pass workspace after a short host-alive probe.
  Empty survey snapshots do not idle or skip PRs and issues. Launchd does not exec
  `lokay-daemon` while `lokay.lock` is held; `LOKAY_PROCESS_HEAD`
  still refuses if HEAD moved under the already-imported daemon.
  Host-ff lives only in Fala. The lokay-daemon shell is OS only (lock, exec,
  logs, bootstrap incident, 180s lock-owner ceiling). Nested Fala SIGALRM
  does not release `lokay.lock`. Detached `issue_to_pr` survives the ceiling.
  Standalone `lokay-daemon` still probes. Healthy first host
  check is not rerun (`gh api user` / ast.parse every lokay module). Repair
  still reruns `_check`.
  Fala inherit_env is a whitelist: every atom, including nested `recovery_factory`,
  must inherit `LOKAY_HOST_FF_FETCHED`. Missing key aborts the lokay.
  Every live Fala sqlite under `~/.lokay/fala/<path>/` is maintained through
  `fala.maintain_journal` when oversized (default 64 MiB) so idle ticks do
  not reopen a multi-GB journal. One oversized journal per tick, smallest
  first, deletes only terminal runs. A journal with no terminal-run candidates
  does not consume the apply slot. VACUUM is Fala-owned and runs only when
  remaining free space can hold the compact copy plus a 16 MiB safety margin.
  Maintenance does not finalize `created` leftovers; that stays on the owning
  recovery path with lease evidence.
  Detached issue-to-PR journals are not finalized. `daemon_entry` /
  `daemon_cycle` / `factory_pass` open a fresh wrapper sqlite per tick and
  prune old wrapper dirs; they do not reopen the shared lokay journals.
  Wrapper directories are retained until completion and recovery dependencies
  are known: allocating a newer wrapper does not delete the older ones.
  Each
  host materializes only the requested path. Nested children never share the tree-root
  sqlite or overwrite a sibling materialized package. The journal is a pass
  trace, not world history. Product recovery stays on `state.jsonl`.
  Over-cap is fail-closed if Fala cannot maintain the file.
  In the CLI product budget, after each factory pass, leftover closeout parks leftover `work:ready` /
  `ai:ready` on GitHub-CLOSED lokay issues. That is not a second hunt through
  every lokay PR; GitHub CLOSED is enough. Lokay repo count never fail-closes
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
  Pytest must not skip leftover GitHub lists using the lokay stamp.
  Legacy survey children retain the 120s empty-survey cache helpers.
  They do not supply an early idle route to the current department parent.
  The live `factory_pass` starts with `host_ff`, then the host gate and
  department nest. The shell does not idle-skip or run leftover probes.
  `leftover_closeout` belongs to the explicit CLI `product_pass_budget`,
  not the daemon parent. Tests must not use the operator's survey stamps.
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
  Pytest must not skip leftover-cache GitHub lists using the lokay stamp.
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
  Pytest must not skip leftover-ready GitHub lists using the lokay stamp.
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
  Pytest must not skip leftover-incident GitHub lists using the lokay stamp.
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
  merge on the live lokay via env.
