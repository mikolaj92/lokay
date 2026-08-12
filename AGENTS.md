# Lokay agent notes

## Design law

**Unix small programs + Fala graph for order + real agent only.**

- See `docs/UNIX.md`, `docs/GRAPH.md`, `docs/WORKING.md`, **`docs/AUTONOMY.md`**, **`docs/NO_STUBS.md`**, **`docs/HTMX.md`**, **`docs/ALPINE.md`**, **`docs/PLATFORM_UI.md`**.
- New capability → `src/lokay/proc/` + `project.scripts`.
- New ordering → `fala/lokay.fala-package.toml` (conduction).
- Do **not** grow `compose/*` with GitHub/git/agent logic beyond wiring.
- JSON on stdout (`envelope.ok` / `envelope.err`).

## Hard bans

- **No** `fake` / `stub` / `mock` / `noop` agent.
- **No** canary-only “fixes” (`LOKAY_CANARY.md` style).
- **No** bare `python3` for product CLI — use **`uv run`**.
- **No** Hermes Kanban as execution ledger.
- **No** hidden SPA / JSON+client-render chrome — server HTML fragments if UI exists (`docs/HTMX.md`).
- **No** app-wide Alpine store / server-state mirrors — local UI only (`docs/ALPINE.md`).
- **No** CDN forks for Basecoat/HTMX/Alpine — product_shell + `/static/platform` if auth UI exists (`docs/PLATFORM_UI.md`).

## Stack

- Executor: **Pi** (`lokay-run-agent`; `executor.command: pi`, model `omniroute/pi`).
- Scope: `repos.mikolaj92.yaml` (managed repos).
- Continuous mill: LaunchAgent `ai.mikolaj.lokay-mill` → `scripts/lokay-mill-daemon.sh`.

## Verify

```bash
uv run pytest -q
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
```
