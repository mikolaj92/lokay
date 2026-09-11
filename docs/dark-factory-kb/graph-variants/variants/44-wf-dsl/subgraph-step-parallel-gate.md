# Subgraph: step-parallel-gate

**Theme:** Engine owns steps / parallel / gate.  
**Mode mix:** 100% DET orchestration.

## Flow

```mermaid
flowchart TD
  A([enter: AST]) --> N[DET: next step / fan-in]
  N --> K{kind?}
  K -->|claude slot| T([yield: tmux-claude])
  K -->|gate auto| G[DET: tests/schema]
  K -->|gate human| H([yield: ticket-to-pr HITL])
  K -->|git/pr atom| P([yield: ticket-to-pr DET])
  G -->|fail + budget| T
  G -->|pass| N
  T --> N

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class N,G det
```

## Notes

- 0 orchestration tokens.
- Claude never chooses next `.wf` step.
