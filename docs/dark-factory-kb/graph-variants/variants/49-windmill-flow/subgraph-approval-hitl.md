# Subgraph: approval-hitl

**Theme:** Native Windmill approval = HITL gate.  
**Mode mix:** HITL (not LLM judge).

## Flow

```mermaid
flowchart TD
  A([enter: approval step]) --> N[DET: notify approver]
  N --> H{human decision}
  H -->|reject| B([back to script-leaves])
  H -->|approve| OK([leave: approved])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class N det
```

## Notes

- Może stać po planie lub przed PR — wg flow.
- Model nie jest jedynym werdyktem.
