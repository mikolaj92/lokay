# Subgraph: workflow-call

**Theme:** Reusable `workflow_call` = stały spine; caller cienki.  
**Mode mix:** 100% DET.

## Flow

```mermaid
flowchart TD
  A([enter: ai:ready bound]) --> C[DET: consumer thin on + uses]
  C --> W[DET: load reusable YAML steps]
  W --> I[DET: wire inputs + secrets]
  I --> F{DET fork: GH_ACTION_AI_AGENT / Copilot?}
  F -->|claude|codex| R([yield: resolver-leaf])
  F -->|copilot| A2([yield: assign-copilot])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class C,W,I,F det
```

## Notes

- **Steps fixed in library YAML** — LLM nie dopisuje `steps:`.
- **Fork by config**, nie przez model.
- **Handoff:** wired job context + which leaf path.
