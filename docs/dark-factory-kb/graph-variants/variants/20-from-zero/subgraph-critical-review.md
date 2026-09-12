# Subgraph: critical-review

**Theme:** krytyczny przegląd PR — osobna rola (SOUL ciężar nr 3).  
**Mode mix:** AGENT review; DET na status CI.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait / fetch CI status]
  B --> C{CI green?}
  C -->|no| D[DET: report CI failure]
  D --> R([leave: changes needed → implement])
  C -->|yes| E[AGENT: critical PR review]
  E --> F[AGENT: check project consistency / architecture fit]
  F --> G[AGENT: write review comments]
  G --> H{approve?}
  H -->|request changes| R
  H -->|yes| I([leave: approved])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D det
  class E,F,G agent
```

## Notes

- **Separate role from implementer.** Critical review is never the same seat that wrote the diff (meat or AI).
- **Architecture fit unless the PR changes architecture.** Consistency with the project; comments are first-class.
- **CI is DET gate.** No AGENT override of red builds on the clear path.
- **Optimistic clarity.** Approve or request changes — no fuzzy maybe-later state in the graph.
- **Handoff contract.** Output = `{approved: true, pr}` or `{approved: false, feedback}` for merge-human / implement loop.
