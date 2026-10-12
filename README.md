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

Environment overrides can go in `~/.config/lokay/env`:
`LOKAY_TICK_SECONDS` (60), `LOKAY_HEARTBEAT_MINUTES` (5),
`LOKAY_NODE_MINUTES` (60), `LOKAY_ALARM_REPO` (`mikolaj92/lokay`).
The service uses the checkout SHA as the heartbeat version after self-update;
manual runs use the installed package version.
