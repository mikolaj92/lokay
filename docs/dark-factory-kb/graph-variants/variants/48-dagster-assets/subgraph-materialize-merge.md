# Subgraph: materialize-merge

**Theme:** Po zmaterializowanym `pr` — HITL / MergePolicy; sensor na approve; merge DET.  
**Mode mix:** DET + HITL. LLM nie jest jedyną bramką merge.

## Flow

```mermaid
flowchart TD
  A([enter: pr asset materialized]) --> B[DET: label ai/pr-open + request reviewers]
  B --> C[DET sensor / wait: approved OR changes OR timeout]
  C -->|changes requested| BACK[DET: RunRequest repair partition]
  BACK --> OUTR([leave: back to llm-op-leaf / sda])
  C -->|timeout / deny| ESC[DET: escalate human / idle]
  C -->|approved| POL{MergePolicy?}
  POL -->|Off| HOLD[HITL: human merges manually]
  POL -->|Classify| CLS[DET: policy classify rules]
  CLS -->|auto ok| M[DET: gh merge / resource]
  CLS -->|needs human| HOLD
  POL -->|Always| M
  M --> DONE([leave: done merged / tip host])
  HOLD --> DONE2([leave: waiting human])
  ESC --> IDLE([leave: idle])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a2a3a,stroke:#7a6ab8,color:#eee8ff
  class B,C,BACK,ESC,POL,CLS,M det
  class HOLD hitl
```

## Notes

- **Coder ceiling już za nami.** Ten subgraph nie re-implementuje — tylko review signal + policy.
- **MergePolicy Off|Classify|Always** (KLEPACZ). Always ≠ L5 bank lights-out — nadal CI/checks i jawna polityka.
- **Sensor, nie chat.** Approve = label / review event → kolejny `RunRequest` na merge job / asset — nie „powiedz botowi w PR”.
- **Opcjonalny review SO** może być osobnym assetem *przed* tym subgraphiem; werdykt modelu nie zastępuje HITL gdy polityka = Off.
- **Sukces.** Zmergowany `ai/PR` na tipie hosta w sensownym oknie — nie sam ładny JSON materializacji.
