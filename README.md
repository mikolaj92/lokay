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
`LOKAY_NODE_MINUTES` (60), `LOKAY_ALARM_REPO` (`mikolaj92/lokay`).
The service uses the checkout SHA as the heartbeat version after self-update;
manual runs use the installed package version.

## Dark factory proof

Run the complete local suite (no package unit tests):

```sh
for scenario in scenarios/*.sh; do
  [ "$scenario" = scenarios/darkfactory-canary.sh ] && continue
  bash -n "$scenario" && bash "$scenario" || exit
done
```

`bash scenarios/darkfactory.sh` runs the real CLI twice in fresh temporary homes.
Each repetition processes two issues, forces red → Fix → green → Merge, then
checks an idle tick. Fake pi, Git, GitHub and a local Decision HTTP server log
calls and reject unexpected operations. It checks persisted states, separate
round logs, SHA-bound checks, heartbeat timestamps and operation counts.
`scenarios/darkfactory_canary.sh` checks the canary with fake GitHub; it does not
prove a real canary run.

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

Local scenario success and real canary success are separate results. Only two
verified merges, both run logs and the between-run heartbeat prove the canary.
