# Subgraph: implement

**Theme:** optional light plan → implement → commit(s) → push.  
**Mode mix:** AGENT for code; DET for git plumbing.

## Flow

```mermaid
flowchart TD
  A([enter: ticket + branch]) --> B{light plan needed?}
  B -->|optional yes| C[AGENT: light plan / breakdown]
  B -->|no / default| D[AGENT: implement]
  C --> D
  D --> E[DET: run local checks if configured]
  E --> F{checks green?}
  F -->|no| D
  F -->|yes| G[DET: stage + commit]
  G --> H{more commits?}
  H -->|yes| D
  H -->|no| I[DET: push branch]
  I --> J([leave: branch pushed])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class E,G,I det
  class C,D agent
```

## Notes

- **Default path skips plan.** Light plan/breakdown is optional AGENT; pragmatic thin prefers going straight to implement when the ticket is clear.
- **Implement is the entropy sink.** Only this node (and optional plan) may rewrite product code.
- **Commits stay DET.** Message from ticket ID + summary; no agent inventing release-note novels unless required by repo hooks.
- **Small loop, not a second product.** Checks → fix → commit is local; no nested “full SDLC” inside implement.
- **Meat or AI.** Same AGENT seat — human pair-programming or coding agent; graph does not care.
- **Handoff contract.** Output = `{branch, commit_shas, summary}` for DET open-PR at top level.

