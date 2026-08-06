# No stubs (binding)

Lokay is a **production mill**. The following are **forbidden** in production
config, LaunchAgent env, and runtime agent selection:

| Forbidden | Why |
| --- | --- |
| `agent: fake` / `stub` / `mock` / `noop` | Do not pretend to fix issues |
| Canary-only agents that write marker files | Not real work |
| Green ticks that claim progress without agent/gh/git mutations | Lies about WORKING |
| Shipping `LOKAY_CANARY.md`-style artifacts as “fixes” | Noise |

## Required

- **Real coding harness only** — currently `executor.agent: grok` (invokes `grok` CLI).
- Config and env that claim `live` must actually enable executor + mill policy you intend.
- Unit tests may use local fakes (`_FakeRunner`) **only inside `tests/`** to mock `gh`/IO — never as the mill agent.

## Enforcement

- `lokay.agent.resolve_agent_kind` / `run_agent` raise on stub names.
- `LOKAY_AGENT=fake|stub|mock|noop` raises at config load.
- Continuous mill LaunchAgent must set `LOKAY_AGENT=grok` (or another **real** harness when added).

If you need a dry pass without mutations, use **`mode: dry-run`** or omit `--live`.
That is not a stub agent — it is an explicit non-mutating mode.
