# Live mill smoke procedure

1. On the mill host, create the live config without committing `config.yaml` or secrets:

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

5. Run a bounded live mill:

   ```bash
   uv run lokay mill --config config.yaml --live --max-passes 3
   ```

   Alternatively, use the configured LaunchAgent, which invokes:

   ```bash
   scripts/lokay-mill-daemon.sh
   ```

6. Read the pass receipt:

   ```bash
   jq '{health, progress, remaining, by_repo}' ~/.lokay/last-pass.json
   ```

7. Optionally configure event wake on a self-hosted Actions runner labeled `lokay-mill`; do not start a second coding fleet.

[`AUTONOMY.md`](AUTONOMY.md) documents live operation, event wake, and the serial mill guarantees.

[`WORKING.md`](WORKING.md) defines healthy pass outcomes and the operator-visible status contract.
