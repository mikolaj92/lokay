# Subgraph: wf-spine

**Theme:** Load + validate `*.wf`; DSL-is-code.  
**Mode mix:** 100% DET.

## Flow

```mermaid
flowchart TD
  A([workflow run]) --> L[DET: load .wf]
  L --> V{schema ok?}
  V -->|no| E([idle / invalid])
  V -->|yes| R[DET: create run_id + AST]
  R --> OK([leave: AST ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class L,R det
```

## Notes

- Zmiana procesu = diff `.wf`, nie chat „dziś inaczej”.
- Reject unknown constructs / LLM-in-route.
