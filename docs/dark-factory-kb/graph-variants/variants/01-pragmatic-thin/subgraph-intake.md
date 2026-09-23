# Subgraph: intake

**Theme:** enter PM → next job → process ticket → ready branch context.  
**Mode mix:** almost all DET; no coding agent here.

## Flow

```mermaid
flowchart TD
  A([enter subgraph]) --> B[DET: authenticate / enter PM]
  B --> C[DET: fetch next job / ticket]
  C --> D{ticket actionable?}
  D -->|no| E[DET: skip / requeue / exit]
  E --> Z([leave: idle])
  D -->|yes| F[DET: normalize ticket fields]
  F --> G[DET: derive branch name]
  G --> H[DET: ensure clean workspace]
  H --> I[DET: create / checkout branch]
  I --> J([leave: ticket + branch ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,F,G,H,I,E det
```

## Notes

- **Thinnest front door.** No triage agent, no epic decomposition — one actionable ticket or exit.
- **Normalize once.** Title, ID, acceptance hints, links become a stable payload for implement.
- **Branch naming is script.** Deterministic from ticket ID + slug; humans/agents do not invent names ad hoc.
- **Fail closed.** If PM auth or next-job fails, stop — do not invent work.
- **Handoff contract.** Output = `{ticket, branch, base_ref}` for implement subgraph.

