# Subgraph: intake-sync

**Theme:** GitHub / Linear → Factory Intake board — DET wejście; work item bez chat-pick.  
**Mode mix:** DET (+ opcjonalny Slack start). Staged half front.

## Flow

```mermaid
flowchart TD
  A([enter: sync tick / webhook / Investigate]) --> B[DET: auth GitHub App + optional Linear]
  B --> C[DET: list new/updated issues → Intake cards]
  C --> D{already has work item?}
  D -->|yes| SKIP[DET: idempotent skip / refresh metadata]
  D -->|no| E[DET: create work item + bind repo]
  E --> F[DET: attach issue body / labels / links]
  F --> G{trusted contributor shortcut?}
  G -->|yes + rules allow| H[DET: stage hint → Triage]
  G -->|no / wait| I[DET: leave on Intake until human Start]
  H --> OUT([leave: triage-plan-gates])
  I --> WAIT([leave: idle wait human Start])
  SKIP --> WAIT
  B -->|creds fail| FAIL[DET: fail closed + surface error]
  FAIL --> WAIT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,C,D,E,F,G,H,I,SKIP det
  class FAIL,WAIT stop
```

## Notes

- **DET sync, nie agent pick.** Intake to board + rules, nie „agent wybiera sobie issue z czatu”.
- **Idempotencja.** Ponowny sync odświeża metadane; nie dubluje work itemów.
- **Rules as code.** Trusted-contributor → Triage vs wait-on-Intake żyje w Factory rules / deployment config — nie w promptcie liścia.
- **Slack optional.** Start sesji ze Slacka = ten sam work item contract.
- **Handoff.** Leave = `{work_item_id, issue_ref, repo, stage: Intake|Triage, reason}`.
