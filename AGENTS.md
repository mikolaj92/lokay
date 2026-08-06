# Lokay agent notes

## Design law

**Unix small programs + Fala graph for order + real agent only.**

- See `docs/UNIX.md`, `docs/GRAPH.md`, `docs/WORKING.md`, **`docs/NO_STUBS.md`**.
- New capability → `src/lokay/proc/` + `project.scripts`.
- New ordering → `fala/lokay.fala-package.toml` (conduction).
- Do **not** grow `compose/*` with GitHub/git/agent logic beyond wiring.
- JSON on stdout (`envelope.ok` / `envelope.err`).

## Hard bans

- **No** `fake` / `stub` / `mock` / `noop` agent.
- **No** canary-only “fixes” (`LOKAY_CANARY.md` style).
- **No** bare `python3` for product CLI — use **`uv run`**.
- **No** Hermes Kanban as execution ledger.

## Stack

- Agent: **Grok** (`lokay-run-agent` / `executor.agent: grok`).
- Scope: `repos.mikolaj92.yaml` (managed repos).
- Continuous mill: LaunchAgent `ai.mikolaj.lokay-mill` → `scripts/lokay-mill-daemon.sh`.

## Verify

```bash
uv run pytest -q
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
```
