# Subgraph: ai-ready

**Theme:** Etykieta `ai:ready` (+ opcjonalny sweep) = jedyny start.  
**Mode mix:** 100% DET.

## Flow

```mermaid
flowchart TD
  E([GitHub event]) --> P{issues.labeled ai:ready?}
  P -->|no| S{schedule backlog-sweep?}
  S -->|no| IDLE([idle / ignore])
  S -->|yes| SW[DET: scan backlog criteria]
  SW --> L[DET: apply label ai:ready]
  L --> OK([leave: ai:ready bound])
  P -->|yes| G[DET: parse label + issue id]
  G --> D{deny list / draft / closed?}
  D -->|deny| IDLE
  D -->|ok| OK

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class SW,L,G det
```

## Notes

- **Label is the ticket pick.** Agent nie wybiera z unlabeled backlogu.
- **Sweep tylko nakłada etykietę** — nie implementuje.
- **Handoff:** `{issue_number, repo, label=ai:ready}` → workflow-call.
