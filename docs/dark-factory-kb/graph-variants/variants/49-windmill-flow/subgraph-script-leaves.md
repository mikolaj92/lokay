# Subgraph: script-leaves

**Theme:** DET scripts + typed LLM script leaves.  
**Mode mix:** DET majority; AGENT only plan/implement.

## Flow

```mermaid
flowchart TD
  A([enter: flow step]) --> K{script kind?}
  K -->|claim/worktree/test/git| D[DET: run script atom]
  K -->|plan / implement| L[AGENT: typed SO script]
  D --> N{next in flow?}
  L --> N
  N -->|more| K
  N -->|approval edge| Y([yield: approval-hitl])
  N -->|PR edge| P([yield: pr-ceiling])
  D -->|fail closed| X([escalate / stop])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class D det
  class L agent
```

## Notes

- LLM nie wybiera następnego modułu flow.
- Meat ≡ AI w tym samym leaf.
