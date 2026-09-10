<!-- spine: spine_deterministic -->
# Microsoft Conductor (`microsoft/conductor`)

**spine:deterministic** · **Confidence: 92** — orkiestracja = YAML + Jinja routes (0 tokenów); LLM tylko w krokach `type: agent`; script/MCP/set/human_gate bez modelu.

## Co to jest

CLI MS do multi-agent workflows (Copilot SDK / Anthropic / eksperymentalne sandboks). Workflow w jednym pliku YAML: routing przez wyrażenia Jinja — **first matching condition wins**. Powtarzalne, wersjonowane w PR, te same lokalnie i w CI. To **nie** artushin/conductor-ai (Rust/tmux) — tu vendor MS, deterministyczny DSL.

## Graf

```mermaid
flowchart TD
  start[$start] --> plan[agent: plan]
  plan --> route{Jinja route}
  route -->|needs_code| impl[agent: implement]
  route -->|clarify| human[human_gate / dialog]
  human --> plan
  impl --> test[script: pytest]
  test -->|exit 0| review[agent: review]
  test -->|nonzero| fix[agent: fix bounded]
  fix --> test
  review --> gate{set / terminate}
  gate -->|success| end[$end success]
  gate -->|failed| fail[$end failed]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Stack | **Python 3.12+** CLI · YAML workflows · MIT ★~427 |
| Trigger | `conductor run <workflow.yaml>` (lokal / CI) |
| Orkiestracja | Jinja conditions, parallel/`for_each`, sub-workflows |
| LLM slot | Kroki `type: agent` (izolowane sesje) |
| Agent-free | `script`, `set`, `mcp` (bez LLM), `terminate`, routing |
| Klepacz? | Tak — przykład plan→implement→test→review jako ticket lane |
| Nie robi | LLM jako router „co dalej?” |

## Linki

- https://github.com/microsoft/conductor
- Announce: https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/
- Docs: `docs/workflow-syntax.md` · examples/
- WAVE3 §6 / mapa §2
