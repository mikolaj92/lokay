# Subgraph: cmd-hitl

**Theme:** `parallelogram` command + `hexagon` human + polityka merge → exit.  
**Mode mix:** DET plumbing + HITL. Zero LLM.

## Flow

```mermaid
flowchart TD
  A([enter: command or human scheduled]) --> B{kind?}
  B -->|parallelogram| C[DET: run script in env]
  B -->|hexagon| H[HITL: present choices / freeform]
  C --> D{exit code / outcome?}
  D -->|0 succeeded| E[DET: capture stdout → context]
  D -->|nonzero| F[DET: outcome=failed + log]
  E --> G([leave: resume engine-routes])
  F --> G
  H --> I{human label?}
  I -->|Approve / Always merge| J[DET: apply merge_policy]
  I -->|Revise / changes| K([leave: edge back to leaf])
  I -->|Off hold / timeout| L[HITL: park — no auto merge]
  J --> M{policy?}
  M -->|merged or PR left open| N([leave: toward exit Msquare])
  M -->|deny| L
  L --> G
  K --> G

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a1a3a,stroke:#8a50b0,color:#f6e8ff
  class C,E,F,J det
  class H,L hitl
```

## Notes

- **Command = DET atom.** `script=` → pick_one_labeled, worktree_add, pytest, commit, push, open_pr, merge_policy exec — bez modelu.
- **Human = hexagon.** Edge `label` = opcje (Approve / Revise / Always / Off). Timeout → `human.default_choice` albo park; nie „LLM zgaduje zgodę”.
- **MergePolicy Off|Classify|Always.** Always/Classify mogą iść DET po review; Off = hexagon trzyma przycisk.
- **Coder ceiling = open PR.** Implement leaf nie merjuje; open_pr + merge to command/HITL.
- **goal_gate na testach.** Czerwony test może zablokować sukces runu mimo dojścia do exit.
- **Handoff contract.** Leave = `{outcome, context_patch, preferred_label?}` → engine-routes albo exit.
