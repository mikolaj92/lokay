# Subgraph: flow-modules

**Theme:** Windmill flow = program; modules as DET composition.  
**Mode mix:** 100% DET topology.

## Flow

```mermaid
flowchart TD
  A([webhook / labeled issue]) --> L[DET: load flow definition]
  L --> V{schema + required scripts?}
  V -->|no| E([idle / config error])
  V -->|yes| R[DET: start run + job ids]
  R --> OK([leave: flow running])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class L,R det
```

## Notes

- Zmiana procesu = diff flow, nie prompt.
- Handoff: `{run_id, issue, path}` → script-leaves.
