# Subgraph: det-steps

**Theme:** CODE Activities / `step.run` — pick, worktree, test, git, open PR, merge_policy. Retries **per step**.  
**Mode mix:** DET spine. Wzywa llm-activity tylko gdy Workflow wskaże LLM step.

## Flow

```mermaid
flowchart TD
  A([enter: CODE step scheduled]) --> B[DET: Activity start + heartbeat]
  B --> C{activity name?}
  C -->|pick_one_labeled| D[DET: list + claim one ready-for-agent]
  D --> E{one issue?}
  E -->|none| IDLE([leave: idle])
  E -->|one| REC[DET: record result → resume Workflow]
  C -->|worktree_add| F[DET: occupancy K=1 / fresh worktree]
  F --> G{free?}
  G -->|live| DEF([leave: defer])
  G -->|dead orphan| ORPH[DET: finish_orphan_PR]
  G -->|free| WT[DET: worktree_add + branch]
  WT --> REC
  ORPH --> REC
  C -->|run_tests| T[DET: pytest / CI local]
  T --> H{green?}
  H -->|green| REC
  H -->|red| R{step attempts left?}
  R -->|yes| LLM([yield: llm-activity repair])
  R -->|exhausted| SKIP([leave: skip / escalate])
  C -->|commit_push_pr| P[DET: commit + push + open_pr]
  P --> REC
  C -->|merge_policy| M[DET: Off|Classify|Always atom]
  M --> HITL([yield: hitl-wait])
  C -->|hydrate_issue| HY[DET: fetch issue body + labels]
  HY --> REC

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,F,ORPH,WT,T,P,M,HY det
```

## Notes

- **Idempotent keys.** `step.run("open_pr", {idempotencyKey})` / Temporal Activity id — ponowny retry nie otwiera drugiego PR.
- **Retry = ten Activity.** Padnięty `run_tests` nie rehydratuje issue od zera; padnięty `open_pr` nie re-implementuje. Memo trzyma sukcesy.
- **Fail closed.** Czerwony test + wyczerpany budżet → skip/escalate receipt, nie gruby mózg.
- **Parallelogram = skrypt.** Te same atomy co WORKING_KLEPACZ_GRAPH: pick / worktree / test / git / PR / merge_policy.
- **Handoff.** Leave idle/defer/skip = receipt w historii; yield llm-activity = `{failure_log, attempt, schema}`; yield hitl = `{pr, policy, checks}`.
