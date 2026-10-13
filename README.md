# lokay

Plan, Build, Check, Fix, Merge. Merge is the only end.

`lokay start` runs the graph in Python (`src/lokay/start.py`), the only runtime.
Plan revisions return to Plan checking; Fix returns to Check. Failed steps retry.

Install the LaunchAgents with `bash scripts/install_service.sh` from a checkout with
`.venv/bin/lokay`. The template is `scripts/ai.mikolaj.lokay2.plist`.
`ai.mikolaj.lokay2` runs the caretaker with KeepAlive, RunAtLoad and a 60-second
ThrottleInterval. The installer retires the old `ai.mikolaj.lokay` label.

Before each service iteration, `scripts/self_update.sh` fast-forwards a clean
`main` checkout in `LOKAY_ROOT` to `origin/main` and runs `uv sync` when HEAD changes.
After a successful update, the caretaker replaces itself with the new script.
It parses the entire script before running, so an update cannot change a running loop.

- `lokay status` prints runs from `~/.lokay/runs/*/*/state.json`.
- `~/.lokay/heartbeat.json` records UTC time, result, version, current repo/issue/node
  and node start time every tick, including during long steps and retries.
  It also reports `idle_reason` (`idle_backoff`, `host_down`, `no_work`),
  `issue_since` (first pick until Merge), `failures` and `last_error`.
  The monitor alarms on blocked idle, at least three failures, an old issue,
  or queued work without a merge past the configured threshold.
- Each Check round posts its result, findings and CI outcome on the PR.
- The separate `ai.mikolaj.lokay2.monitor` LaunchAgent runs `lokay monitor` every
  60 seconds, even when the factory stops. It opens one `lokay-stalled` issue while
  an alarm remains open. The factory excludes this issue from its queue.
- Logs use `~/.lokay/logs/lokay.log`; the caretaker rotates at 10 MiB to `lokay.log.1`
  between runs. A single long run can exceed this limit.
- Merged worktrees are removed by the existing Merge step.

Decision defaults to `LOKAY2_DECISION_API=mini` and
`LOKAY2_DECISION_BASE_URL=http://192.168.1.52:8005`.
Mini uses `/v1/decisions` without a model; the host probe requires `/health` to
return HTTP 200 with `"ready": true`.

Environment overrides can go in `~/.config/lokay/env`:
`LOKAY_TICK_SECONDS` (60), `LOKAY_HEARTBEAT_MINUTES` (5),
`LOKAY_NODE_MINUTES` (60), `LOKAY_ISSUE_MINUTES` (60),
`LOKAY_MERGE_HOURS` (1), `LOKAY_ALARM_REPO` (`mikolaj92/lokay`).
The service uses the checkout SHA as the heartbeat version after self-update;
manual runs use the installed package version.

## Dark factory proof

Run the complete local suite (no package unit tests):

```sh
bash scripts/check.sh
```

`repos.yaml` uses the same explicit inventory in `scripts/check.sh`. Missing files
fail before any scenario runs; a red scenario stops the check. The summary counts
executed/required scenarios. Only the live, separately authorized canary is excluded.
`scenarios/suite.sh` verifies inventory completeness, missing/red failure paths,
and stale external configuration → repaired configuration reload, in temporary files.

The old `scenarios/manifest.sh` was deleted in `df81eb38` together with the Fala
manifest it inspected. It is not a lost Python runner test. `3f9097e2` removed its
stale reference, but still checked only 11 scenarios. The full inventory includes
Build, Fix, graph transitions in darkfactory, guards and observability instead of
restoring an obsolete manifest test. A copied historical check command still fails
with exit 127; use the configured check command above.

### Checkout configuration is not host configuration

`load_repos()` reads `LOKAY2_REPOS_FILE`, or `ROOT/repos.yaml` when unset.
`ROOT` belongs to the installed Python package, not necessarily the PR checkout.
Changing the PR's `repos.yaml` does not update a copied host file. Record the
runner's effective path, `mikolaj92/lokay` test argv, PR number and head SHA;
the current shell's environment alone does not prove the runner's configuration.
Do not dump the environment or read credentials.

If the effective file contains the historical loop, ask the host owner to
replace **only** that repo's `test` with `["bash", "scripts/check.sh"]`.
Preserve the old value for rollback and leave every other entry unchanged.
Host edits and agent restarts require separate authorization.

After authorization, let the existing runner resume PR #1784 with
`LOKAY2_REPO=mikolaj92/lokay` and `LOKAY2_ISSUE=1759`. Do not open another PR.
`resume()` reloads the repo configuration and reads the PR's current head SHA.
Persisted local CI is reusable only when both SHA and exact test argv match.
A changed argv or legacy state without argv forces a new local check, even on
an unchanged SHA. The new result replaces the cache through normal state writes;
round logs remain intact. No extra commit is needed to invalidate this cache.
`scenarios/ci.sh` exercises production resume with temporary configuration and
state, real local commands, and fake external Git/PR operations.
An already running `_finish()` holds its test argv locally; its internal Check
retry does not reload that list. Use a new runner invocation/resume after the
active invocation ends, not a concurrent runner or a manual state edit.
`lokay start --check` only probes host readiness; it does not execute the suite.
Require the runner's Check log to show `bash scripts/check.sh` and the full
summary on the final PR SHA. A manual green suite is not that evidence.

`bash scenarios/darkfactory.sh` runs two repetitions in fresh temporary homes.
Each repetition keeps one CLI process for both ticks and the idle tick.
It processes two issues, forces red → Fix → green → Merge, then
checks an idle tick. Fake pi, Git, GitHub and a local Decision HTTP server log
calls and reject unexpected operations. It checks persisted states, separate
round logs, SHA-bound checks, heartbeat timestamps and operation counts. It compares
the complete ordered external call trace across repetitions. Mutation checks reject
missing Fix, merge with red CI and missing second tick. Python network calls and
the runner's curl health probe are restricted to loopback in this scenario.
`scenarios/darkfactory_canary.sh` checks the canary with fake GitHub; it does not
prove a real canary run.

Report the deterministic counters separately: `autonomous_runs=2/2`,
`mutations_rejected=3/3`, `rounds_logs=2/2`, `between_run_heartbeat=1/1`.
For the sandbox, measure `merged_prs=2/2`, `rounds_logs=2/2`,
`between_run_heartbeat=1/1` and `next_scheduled_pair=1/1` separately.
Fake recurrence checks do not confirm a scheduled LaunchAgent cycle.
An unmeasured counter is unconfirmed, not successful. Attribute runner evidence
to `(mikolaj92/lokay, PR #1784, final SHA)`; a local suite is separate evidence.

### Real canary (separate authorization required)

No canary is enabled by installation. After explicit authorization, use the
existing `ai.mikolaj.lokay2` LaunchAgent, not another scheduler. Its template is
`scripts/ai.mikolaj.lokay2.plist`; installation writes
`~/Library/LaunchAgents/ai.mikolaj.lokay2.plist`.

Prerequisites: a Mini with pi and Decision available, an existing authenticated
`gh` session with issue/PR write and merge permissions in
`mikolaj92/lokay-sandbox`, and a sandbox clone in the configured repos file.
Configure the sandbox test command to run both generated scripts, for example
`[python3, -m, unittest, discover, -p, test_darkfactory_*.py]`.
The sandbox must allow automatic merge. Do not put credentials in scripts or
proof artifacts.

Set these in the existing `~/.config/lokay/env` only after authorization:

```sh
LOKAY_DARKFACTORY_CANARY=1
LOKAY2_REPO=mikolaj92/lokay-sandbox
```

The caretaker invokes `scenarios/darkfactory-canary.sh` before each normal tick.
It creates a slugify/version issue pair at most once every 24 hours. An unfinished
pair blocks new pairs. Titles contain a persisted pair ID, so a retry recovers
an issue created before local persistence failed. An advisory lock blocks
concurrent creation. Existing open canary issues without local state block
creation rather than silently starting another pair.

Evidence lives in `~/.lokay/darkfactory-canary/<pair>/`: `proof.json` contains
both merged PR URLs, run paths and SHAs; each issue directory copies the runner's
`state.json` and `rounds.md`. `heartbeat-between.json` is captured after the first
merge and must precede the second merge. The script never edits runner artifacts.
`~/.lokay/darkfactory-canary/state.json` records progress and errors; caretaker
logs remain in `~/.lokay/logs/lokay.log`. Missing between-run heartbeat is a
failure, even if two PRs merged. Retain evidence and investigate errors before
retrying; do not synthesize missing evidence.

Disable pair creation by setting `LOKAY_DARKFACTORY_CANARY=0` in the same env
file. The caretaker reads it on startup, so restart the existing agent only
with authorization. To stop all factory work, unload that existing agent with
`launchctl bootout gui/$(id -u)/ai.mikolaj.lokay2` (also requires authorization).
Disabling creation does not cancel already opened issues.

Report evidence against `(mikolaj92/lokay, PR #1784, final SHA)` separately:

| Gate | Required counters | Evidence |
| --- | --- | --- |
| Local suite | `scenarios=21/21; errors=0` | Full check summary |
| Deterministic cycle | `autonomous_runs=2/2; mutations_rejected=3/3` | Same-process ticks, fake call trace, states, logs, heartbeat |
| Runner Check | Full suite on final SHA | Effective config path, argv and existing PR's Check log |
| Real canary | `merged_prs=2/2; rounds_logs=2/2; between_run_heartbeat=1/1` | Sandbox PR URLs and saved proof |
| Real recurrence | One next pair due, no duplicates | Persisted deadline and existing LaunchAgent log |

The fake canary scenario checks recovery, evidence collection, deadlines and
failure handling. Its simulated clock/state does not prove real recurrence.
Observe the next real pair without changing the clock or invoking a manual tick.
Before the deadline expect no new pair; afterwards expect exactly one. Active
pairs and failures must not create duplicates. Missing evidence stays unverified.
Only two verified merges, both run logs and the between-run heartbeat prove
the real canary. Local green results cannot replace these counters.
