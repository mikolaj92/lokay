# Live lokay smoke procedure

1. On the lokay host, create the live config without committing `config.yaml` or secrets:

   ```bash
   cd ~/Developer/OSS/lokay
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
   uv run lokay lokay --config config.yaml --live --max-passes 3
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

[`AUTONOMY.md`](AUTONOMY.md) documents live operation, event wake, and the serial lokay guarantees.

[`WORKING.md`](WORKING.md) defines healthy pass outcomes and the operator-visible status contract.
