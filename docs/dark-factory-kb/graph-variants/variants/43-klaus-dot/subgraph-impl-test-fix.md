# Subgraph: impl-test-fix

**Theme:** Implement → Test/Lint → CheckResults → Fix bounded.  
**Mode mix:** AGENT boxes + DET shell/diamond.

## Flow

```mermaid
flowchart TD
  A([enter: Implement]) --> I[AGENT: Implement]
  I --> T[DET: Test shell]
  T --> L[DET: Lint shell]
  L --> C{DET CheckResults}
  C -->|ok| OK([leave: ready ceiling])
  C -->|fail + budget| F[AGENT: Fix]
  F --> T
  C -->|budget out| X([idle / escalate])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class T,L,C det
  class I,F agent
```

## Notes

- Fix loop bounded (`fix_loop_n`).
- Fail closed — nie limbo.
