# Lokay lite

**Issue triage → real coding agent (Grok) → PR → PR triage → main**, as Unix atoms + optional Fala graphs.

| Binding docs | |
| --- | --- |
| [`docs/WORKING.md`](docs/WORKING.md) | When the machine is WORKING |
| [`docs/NO_STUBS.md`](docs/NO_STUBS.md) | **No fake/stub agents** |
| [`docs/UNIX.md`](docs/UNIX.md) | Small processes |
| [`docs/GRAPH.md`](docs/GRAPH.md) | Fala / path order |
| [`repos.mikolaj92.yaml`](repos.mikolaj92.yaml) | Managed repos (scope) |

## Install

```bash
cd ~/Developer/OSS/lokay
uv sync
uv run pytest -q
```

## Continuous mill (this machine)

LaunchAgent **`ai.mikolaj.lokay-mill`** runs every **10 minutes**:

```bash
launchctl print "gui/$(id -u)/ai.mikolaj.lokay-mill" | head -25
tail -f ~/.lokay/logs/mill-latest.log
```

Env (production): `LOKAY_MODE=live`, `LOKAY_EXECUTOR_ENABLED=1`, **`LOKAY_AGENT=grok`**, merge on.

**Do not set `LOKAY_AGENT=fake`.** It is rejected at runtime.

## Manual

```bash
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
uv run lokay-mill --config config.yaml --live --max-passes 8
```

Dry-run (no mutations): omit `--live` / use `mode: dry-run` — still **not** a stub agent.

## Layout

```text
repos.mikolaj92.yaml   # which repos we mill
fala/                  # declarative graphs
src/lokay/proc/        # atomic CLIs
src/lokay/compose/     # tick / mill / status
scripts/lokay-mill-daemon.sh
docs/NO_STUBS.md
```

## Safety

- Real agent only (Grok)
- No force-push / repo delete / raw curl
- Issue body is untrusted evidence in prompts
