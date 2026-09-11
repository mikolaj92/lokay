# Subgraph: sensor-github-labels

**Theme:** GitHub label → Dagster **Sensor** → `RunRequest` (partition = issue). Start DET; zero chat-pick.  
**Mode mix:** DET only. Sensor nie woła LLM.

## Flow

```mermaid
flowchart TD
  A([enter: GH webhook / poll tick]) --> B[DET: list issues with label ready-for-agent]
  B --> C{already running / materialized?}
  C -->|yes skip| SKIP[DET: cursor advance / no RunRequest]
  C -->|new eligible| D[DET: check occupancy K=1 / worktree free]
  D -->|busy| HOLD[DET: defer / requeue later]
  D -->|free| E[DET: yield RunRequest partition_key=issue_id]
  E --> F[DET: optional label ai/in-progress]
  F --> OUT([leave: job scheduled])
  SKIP --> IDLE([leave: idle])
  HOLD --> IDLE
  B -->|none| IDLE

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E,F,SKIP,HOLD det
```

## Notes

- **Label = kontrakt startu.** `ready-for-agent` (kanon KLEPACZ) — nie „agent znalazł coś na czacie”.
- **Partition = issue_id.** Jedna partycja → jeden łańcuch SDA → jeden PR (K=1).
- **Sensor idempotentny.** Cursor / tags unikają podwójnego `RunRequest` na ten sam label event.
- **No LLM in sensor.** Ocena „czy brać” = reguły DET (label, occupancy, skip jeśli `pr` już zmaterializowany).
- **Handoff.** Leave = `RunRequest` + tags `{issue_id, label}` → job materializuje selection ticket→…→pr.
