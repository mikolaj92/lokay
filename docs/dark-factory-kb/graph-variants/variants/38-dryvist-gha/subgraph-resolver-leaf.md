# Subgraph: resolver-leaf

**Theme:** Claude/Codex jako liść `cc-issue-resolver` / `run-ai-agent` → draft PR.  
**Mode mix:** DET harness + AGENT leaf.

## Flow

```mermaid
flowchart TD
  A([enter: resolver path]) --> H[DET: checkout worktree / env]
  H --> L[AGENT: resolve issue → code]
  L --> T{DET: tests / ask-or-stop?}
  T -->|fail| S([comment + skip])
  T -->|ok| P[DET: open draft PR]
  P --> H2([leave: PR draft — MergePolicy Off])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class H,T,P det
  class L agent
```

## Notes

- **Entropy tylko w liściu.** Harness = claim/worktree/PR.
- **Coder ceiling = draft PR**, nie merge.
- **Meat ≡ AI** — to samo siedzenie gdy człowiek wypełnia liść.
