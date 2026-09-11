# Subgraph: plan

**Theme:** job `plan` — AGENT leaf + `plan.json` artifact.  
**Mode mix:** DET job shell + AGENT leaf.

## Flow

```mermaid
flowchart TD
  A([enter: bound ticket]) --> H[DET: checkout + env]
  H --> P[AGENT: plan SO]
  P --> U[DET: upload-artifact plan.json]
  U --> OK([leave: plan artifact])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class H,U det
  class P agent
```

## Notes

- LLM nie dopisuje `jobs:` / `needs:`.
- Jedyny handoff dalej = artifact.
