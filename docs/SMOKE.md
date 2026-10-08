# Live lokay smoke procedure

1. On the lokay host, create the live config without committing `config.yaml` or secrets:

   ```bash
   cd "${LOKAY_ROOT:-$HOME/Developer/lokay/main}"
   cp config.live-autonomous.example.yaml config.yaml
   ```

2. Sync the checkout:

   ```bash
   uv sync
   ```

3. Check fleet status:

   ```bash
   uv run lokay status --config config.yaml
   ```

4. Check local readiness and the latest pass:

   ```bash
   uv run lokay status --config config.yaml --local
   ```

5. Run a bounded live lokay:

   ```bash
   uv run lokay work --config config.yaml --live --max-passes 3
   ```

   Alternatively, use the configured LaunchAgent, which invokes:

   ```bash
   scripts/lokay-service.sh
   ```

6. Read the pass receipt:

   ```bash
   jq '{health, progress, remaining, by_repo}' ~/.lokay/last-pass.json
   ```

7. Verify the local LaunchAgent heartbeat; do not configure GitHub Actions or start a second coding fleet.

For a separately classified unbounded collector seed, this smoke run remains a
PR lokay only: it must not populate collection data or wait for the collector.
The destination collector patch starts its durable background process after
merge; assess whether it accrues in a later issue.

[`AUTONOMY.md`](AUTONOMY.md) documents live operation, the local LaunchAgent heartbeat, and the serial lokay guarantees.

[`WORKING.md`](WORKING.md) defines healthy pass outcomes and the operator-visible status contract.

## Mini tip smoke (mini-m4-0 hop return)

SHOULD path when the mini-m4-0 hop returns. Host-only checks; no plist and no
secrets enter the repo.

1. One LaunchAgent label. Legacy `ai.mikolaj.lokay-mill` stays absent:

   ```bash
   launchctl list | grep 'ai.mikolaj.lokay'   # exactly: ai.mikolaj.lokay
   launchctl bootout "gui/$(id -u)/ai.mikolaj.lokay-mill" 2>/dev/null || true
   ```

2. Kick the agent. One heartbeat runs host_ff (fetch + ff-only) before work:

   ```bash
   launchctl kickstart -k "gui/$(id -u)/ai.mikolaj.lokay"
   ```

3. After the pass, the tip is `origin/main` and at or above the review SHA:

   ```bash
   LOKAY_ROOT="${LOKAY_ROOT:-$HOME/Developer/lokay/main}"
   test "$(git -C "$LOKAY_ROOT" rev-parse HEAD)" = "$(git -C "$LOKAY_ROOT" rev-parse origin/main)" && echo tip=origin/main
   git -C "$LOKAY_ROOT" merge-base --is-ancestor <review-sha> HEAD && echo tip>=review
   ```

4. The heartbeat receipt is fresh (mtime after the kick):

   ```bash
   jq '{health, progress, ts}' ~/.lokay/last-pass.json
   stat -f '%Sm' ~/.lokay/last-pass.json
   ```

If `HEAD` still lags `origin/main`, kick once more before investigating;
`last-pass.json` with `health: host_updated` proves the ff-only pass ran.
