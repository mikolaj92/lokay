# Subgraph: dispatch

**Theme:** Guild Dispatcher — events/labels → exactly one actionable job.  
**Mode mix:** all DET; no coding agent; no chat intake.

## Flow

```mermaid
flowchart TD
  A([enter subgraph]) --> B[DET: authenticate PM / VCS webhooks]
  B --> C[DET: list labeled jobs e.g. ready-for-agent / guild-auto]
  C --> D{any actionable?}
  D -->|no| E[DET: record idle]
  E --> Z([leave: idle])
  D -->|yes| F[DET: pick exactly one K=1]
  F --> G{repo / worktree free?}
  G -->|occupied live| H[DET: defer]
  H --> Z
  G -->|free| I[DET: normalize ticket payload]
  I --> J[DET: claim / lock seat]
  J --> K([leave: one job ready for Planner])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,E,F,H,I,J det
```

## Notes

- **Label = start.** Zero „weź z czatu”; tylko etykieta / event (Guild: `guild-auto`-style).
- **K=1.** Dispatcher never fans out parallel implementers for one mill tick.
- **Fail closed.** Auth or list failure → idle; do not invent work.
- **Handoff contract.** Output = `{ticket, source_event, base_ref}` for Planner.
- **Polish:** dyspozytor to skrypt, nie mózg — kolejka i etykieta, bez routingu agentowego.
