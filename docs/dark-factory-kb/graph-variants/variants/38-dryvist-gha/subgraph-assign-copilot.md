# Subgraph: assign-copilot

**Theme:** `ai:ready` → assign Copilot Coding Agent → `ai:assigned` → Draft PR.  
**Mode mix:** DET label/assign + bot leaf.

## Flow

```mermaid
flowchart TD
  A([enter: Copilot path]) --> AS[DET: assign Copilot agent]
  AS --> FL[DET: flip label ai:assigned]
  FL --> B[BOT leaf: implement + Draft PR]
  B --> F{ok?}
  F -->|no| S([comment + skip])
  F -->|yes| H([leave: PR draft — MergePolicy Off])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class AS,FL det
  class B agent
```

## Notes

- **Assign/label flip = DET.** Bot = entropy leaf.
- **Opcjonalny `_ai-merge-gate`** to gate, nie lights-out (default Merge Off).
- **Handoff:** draft PR URL + issue id.
