# Subgraph: implement

**Theme:** jak najlepiej zaimplementować — tu wkracza entropia.  
**Mode mix:** AGENT implement; opcjonalny lekki plan; DET tylko na lokalne checki.

## Flow

```mermaid
flowchart TD
  A([enter: ticket ready]) --> B{light plan needed?}
  B -->|optional yes| C[AGENT: plan how to do this issue]
  B -->|no / default| D[AGENT: implement]
  C --> D
  D --> E[DET: local checks if configured]
  E --> F{checks green?}
  F -->|no| D
  F -->|yes| G([leave: code ready for git])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class E det
  class C,D agent
```

## Notes

- **This is SOUL ciężar nr 2.** Not a script take-next — judgment on how to implement.
- **Narrow agents OK.** Plan-only or file-breakdown agents are fine; not one fat brain tool-calling everything.
- **Default skips plan.** Optimistic clarity: clear ticket → go straight to implement.
- **Meat ≡ AI.** Same AGENT seat — human or coding agent; graph does not care.
- **No git here.** Branch/commit/push live in git-pr so this subgraph stays about code judgment.
- **Handoff contract.** Output = `{workspace_diff_summary, ready_for_git: true}` for git-pr.
