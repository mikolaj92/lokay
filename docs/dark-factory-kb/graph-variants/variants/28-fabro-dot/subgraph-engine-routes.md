# Subgraph: engine-routes

**Theme:** Fabro engine wybiera **następny węzeł** — 0 tokenów orkiestracji.  
**Mode mix:** 100% DET. Zero LLM w routingu.

## Flow

```mermaid
flowchart TD
  A([enter: stage outcome + context]) --> B[DET: collect outgoing edges]
  B --> C[DET: eval condition / preferred_label / weight]
  C --> D{first matching edge?}
  D -->|box or tab| E([leave: schedule sandbox-agent])
  D -->|parallelogram / wait| F([leave: schedule cmd-hitl])
  D -->|hexagon| G([leave: schedule human gate])
  D -->|diamond only| H[DET: resolve nested conditions]
  H --> C
  D -->|to exit| I([leave: toward Msquare])
  D -->|none / stall| J([leave: idle / escalate])
  D -->|max_visits / signature limit| K([leave: fail-closed escape])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,H det
```

## Notes

- **Engine owns next.** Po `succeeded` / `failed` / `partially_succeeded` / `skipped` silnik ewaluuje `condition` (`outcome=…`, `context.KEY`, `preferred_label`). LLM **nie** woła „następnego toola ze świata”.
- **0 tokenów.** Routing = wyrażenie + weight tiebreak (`selection=deterministic` default) — jak Jinja w Conductorze, tu natywne Fabro.
- **Loops OK, ale bound.** `implement → test → gate → implement` z `max_visits` / `loop_restart_signature_limit` — bez nieskończonego limbo.
- **goal_gate.** Czerwony test z `goal_gate=true` może oblać run nawet przy dojściu do exit — fail closed.
- **Nie mylić z agent routing schema.** `output_schema="routing"` w Fabro to opcjonalny leaf hint; w klepaczu **preferujemy** czyste DET conditions — SO review/plan nie steruje topologią.
- **Handoff contract.** Leave = `{next_node_id, edge_label?, reason}` → sandbox-agent | cmd-hitl | exit.
