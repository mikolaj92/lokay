<!-- spine: spine_deterministic -->
# fabro-sh/fabro

**Confidence: 80** — „software factory” z DOT/graph + sandboxes; HITL gates — real mill, nie czysty głupi klepacz.

## Co to jest

Platforma workflow-as-graph, sandboxes (Daytona), git checkpoints. Marketing dark factory, ale bramki ludzkie uczciwe.

## Graf

```mermaid
flowchart TD
  signal[Issue/spec] --> graph[DOT / workflow graph]
  graph --> sand[Sandbox agent steps]
  sand --> cp[Git checkpoints]
  cp --> hitl{Human gate?}
  hitl -->|tak| human[Approve]
  hitl -->|nie| next[Next node]
  human --> next
  next --> pr[PR / deliver]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | API/UI + graph |
| Sandbox | Daytona / remote |
| Merge | Często HITL |
| Risk | Szerszy niż sama mrówka label→PR |

## Linki

- https://github.com/fabro-sh/fabro
