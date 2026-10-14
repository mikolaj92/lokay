# lokay

Plan, Build, Check, Fix, Merge. Merge is the only end.

`lokay start` runs the graph in Python (`src/lokay/start.py`), the only runtime.
Plan revisions return to Plan checking; Fix returns to Check. Failed steps retry.

Analiza przypiętej rewizji: [maszyna stanów](STATE_MACHINE.md),
[ryzyka R1–R25](RISKS.md) i [weryfikacja incydentów](INCIDENTS.md).

Install the LaunchAgents with `bash scripts/install_service.sh` from a checkout with
`.venv/bin/lokay`. The template is `scripts/ai.mikolaj.lokay2.plist`.
`ai.mikolaj.lokay2` runs the caretaker with KeepAlive, RunAtLoad and a 60-second
ThrottleInterval. The installer retires the old `ai.mikolaj.lokay` label.

Before each service iteration, `scripts/self_update.sh` fast-forwards a clean
`main` checkout in `LOKAY_ROOT` to `origin/main` and runs `uv sync` when HEAD changes.
After a successful update, the caretaker replaces itself with the new script.
It parses the entire script before running, so an update cannot change a running loop.

- `lokay status` prints runs from `~/.lokay/runs/*/*/state.json`.
- Ticks log calls and transitions in `~/.lokay/ticks/`, with large values in `blobs/`.
  `uv run lokay replay <file.jsonl|file.jsonl.gz|dir> [--repo R --issue N]` verifies transitions without external calls.
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

`LOKAY_TICK_BUDGET` sets the tick budget in seconds (default: `2700`).
It must be a numeric string representing finite positive seconds; invalid values
stop the tick before queue selection. For example, `LOKAY_TICK_BUDGET=0.25`
sets a quarter-second budget. A shared monotonic deadline starts before queue
selection. Plan, Check/Fix, Merge and process retries stop starting work at the
deadline. The saved node, SHA, findings and Plan phase resume on the next tick;
the tick owner releases its lock even if saving fails.

Process calls use the minimum of their operation timeout, 3600 seconds and the
remaining tick budget. GitHub calls use 60 seconds; setup/local CI use 600 seconds.
Timed-out process groups are killed. Output draining and process reaping share
a five-second cleanup budget. Tick expiry saves `pending`, without failure
backoff; an operation timeout remains an ordinary error. Retry waits stop at the
deadline. This is not a hard wall-clock limit on filesystem operations or guard
cleanup.

Ready repositories are ordered by their latest persisted attempt, oldest first.
Each repository saves `runs/<repo>/attempt.json` under its lock before fetching
its queue, so API failures and budget exhaustion also rotate selection. Existing
issue timestamps remain a fallback. Missing timestamps count as zero; ties use
repository name. Within a repository, PRs retain priority and use oldest issue
attempt, then PR number.
The attempt timestamp is saved before processing, including failed or exhausted
ticks. An issue-only repository now competes with PR repositories, but continuous
PR arrivals **can still starve issues within the same repository**.
For two ready repositories with the default budget, estimate the second
repository's wait as about 2700 seconds + cleanup + the service interval.
This is not a one-hour guarantee for arbitrary budgets, more repositories, host
failures or unbounded filesystem I/O. Production timing has not been measured.

## Dashboard

Read-only LAN dashboard: <http://192.168.1.52:8010/>. HTML refreshes every 60
seconds; `/api/state.json` exposes the same snapshot and `/healthz` returns `ok`.
GitHub reads run in the background every 300 seconds, with a persistent cache.
No runtime LLM calls. Keep this unauthenticated page on a trusted LAN.

Run `bash scripts/lokay-dashboard.sh`, or install the LaunchAgent (the checkout
must be available at `~/.lokay/host`, with its dependencies installed):

```sh
cp scripts/ai.mikolaj.lokay2-dashboard.plist ~/Library/LaunchAgents/ && launchctl load -w ~/Library/LaunchAgents/ai.mikolaj.lokay2-dashboard.plist
```

Overrides: `LOKAY_HOME`, `LOKAY_REPOS_YAML`, `LOKAY_DASHBOARD_REFRESH` (seconds),
`LOKAY_DASHBOARD_PORT`, `LOKAY2_PROVIDER`, and `LOKAY2_MODEL`.
Times and ETA dates use Europe/Warsaw. GitHub list limits can undercount busy
repositories; the page states the limits.

## Dark factory proof

Run the complete local suite (no package unit tests):

```sh
bash scripts/check.sh
```

The check first prepares this checkout with `uv sync --frozen` and verifies local
`lokay` and `yaml` imports. Initial preparation may require network access;
an unavailable dependency fails the check. It then isolates the home, temporary
directory and uv cache inside the checkout and runs
`uv run lokay replay fixtures/replay/` offline, without syncing dependencies.
An unexpected GitHub CLI call fails without logging its arguments.
Replay checks recorded transitions and stops at the first mismatch.
Blobs may be plain or gzip-compressed.

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
An already running `_finish()` holds its test argv locally; its internal Check
retry does not reload that list. Use a new runner invocation/resume after the
active invocation ends, not a concurrent runner or a manual state edit.
`lokay start --check` only probes host readiness; it does not execute the suite.
Require the runner's Check log to show `bash scripts/check.sh` and the full
summary on the final PR SHA. A manual green suite is not that evidence.

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

The caretaker invokes `scripts/darkfactory-canary.sh` before each normal tick.
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
| Local replay | `replay: 129/129 transitions ok` | Full check summary |
| Runner Check | Full suite on final SHA | Effective config path, argv and existing PR's Check log |
| Real canary | `merged_prs=2/2; rounds_logs=2/2; between_run_heartbeat=1/1` | Sandbox PR URLs and saved proof |
| Real recurrence | One next pair due, no duplicates | Persisted deadline and existing LaunchAgent log |

Replay does not prove real recurrence.
Observe the next real pair without changing the clock or invoking a manual tick.
Before the deadline expect no new pair; afterwards expect exactly one. Active
pairs and failures must not create duplicates. Missing evidence stays unverified.
Only two verified merges, both run logs and the between-run heartbeat prove
the real canary. Local green results cannot replace these counters.
