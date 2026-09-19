# Subgraph: trigger

**Theme:** `issue_comment` / `workflow_dispatch` = start.  
**Mode mix:** 100% DET.

## Flow

```mermaid
flowchart TD
  E([GitHub event]) --> C{issue_comment slash /klepacz|/plan|/do?}
  C -->|no| D{workflow_dispatch + issue_number?}
  D -->|no| IDLE([idle / ignore])
  D -->|yes| OK([leave: bound ticket])
  C -->|yes + if gates| G[DET: parse issue + policy input]
  G --> X{deny / closed?}
  X -->|deny| IDLE
  X -->|ok| OK

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class G det
```

## Notes

- Agent nie pickuje unlabeled backlogu.
- Handoff: `{issue_number, merge_policy?}` → job plan.
