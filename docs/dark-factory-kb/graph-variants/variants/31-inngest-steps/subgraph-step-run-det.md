# Subgraph: step-run-det

**Theme:** CODE `step.run` — hydrate, pick/claim, worktree, test, git, open PR, merge_policy. Retries **per step**.  
**Mode mix:** DET spine. Wzywa step-run-llm tylko gdy function body wskaże LLM step.

## Flow

```mermaid
flowchart TD
  A([enter: CODE step.run scheduled]) --> B[DET: step.run name + memo key]
  B --> C{step name?}
  C -->|hydrate| HY[DET: fetch issue body + labels]
  HY --> REC[DET: return → memo → resume fn]
  C -->|claim-one| D[DET: list + claim one ready-for-agent]
  D --> E{one issue?}
  E -->|none| IDLE([leave: idle])
  E -->|one| REC
  C -->|worktree| F[DET: occupancy K=1 / fresh worktree + branch]
  F --> G{free?}
  G -->|live| DEF([leave: defer])
  G -->|dead orphan| ORPH[DET: finish_orphan_PR]
  G -->|free| WT[DET: worktree_add]
  WT --> REC
  ORPH --> REC
  C -->|run-tests| T[DET: pytest / CI local]
  T --> H{green?}
  H -->|green| REC
  H -->|red| R{attempts left?}
  R -->|yes| LLM([yield: step-run-llm repair])
  R -->|exhausted| SKIP([leave: skip / escalate])
  C -->|commit-push-pr| P[DET: commit + push + open_pr]
  P --> REC
  C -->|merge-policy| M[DET: Off|Classify|Always atom]
  M --> HITL([yield: wait-merge])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,HY,D,F,ORPH,WT,T,P,M det
```

## Notes

- **Named steps = idempotency.** `step.run("open-pr", …)` — ponowny retry funkcji nie otwiera drugiego PR; memo trzyma URL.
- **Retry = ten step.** Padnięty `run-tests` nie rehydratuje; padnięty `open-pr` nie re-implementuje.
- **Fail closed.** Czerwony test + wyczerpany budżet → skip/escalate receipt, nie gruby mózg.
- **Parallelogram = skrypt.** Te same atomy co WORKING_KLEPACZ_GRAPH: claim / worktree / test / git / PR / merge_policy.
- **Handoff.** Leave idle/defer/skip = receipt w memo; yield step-run-llm = `{failure_log, attempt, schema}`; yield wait-merge = `{pr, policy, checks}`.
