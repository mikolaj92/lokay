# Subgraph: task-det

**Theme:** CODE `@task` — hydrate, claim K=1, worktree, test, commit/push, open_pr, merge_policy. Retries **per task**.  
**Mode mix:** DET spine. Wzywa task-llm tylko gdy `@flow` wskaże plan/impl.

## Flow

```mermaid
flowchart TD
  A([enter: CODE @task scheduled]) --> B[DET: @task name + persist/cache key]
  B --> C{task name?}
  C -->|hydrate| HY[DET: fetch issue body + labels]
  HY --> REC[DET: return → persist → resume @flow]
  C -->|claim-one| D[DET: list + claim one ready-for-agent]
  D --> E{one issue?}
  E -->|none| IDLE([leave: idle])
  E -->|one| REC
  C -->|worktree| F[DET: occupancy K=1 / branch]
  F --> G{free?}
  G -->|busy| DEF([leave: defer])
  G -->|orphan| ORPH[DET: finish_orphan_PR]
  G -->|free| WT[DET: worktree_add]
  WT --> REC
  ORPH --> REC
  C -->|run_tests| T[DET: pytest / local CI]
  T --> H{green?}
  H -->|green| REC
  H -->|red| R{attempts left?}
  R -->|yes| LLM([yield: task-llm implement repair])
  R -->|exhausted| SKIP([leave: skip / escalate])
  C -->|commit_push| P[DET: git commit + push]
  P --> REC
  C -->|open_pr| PR[DET: gh pr create ai/PR]
  PR --> ART([yield: artifacts-pr])
  C -->|merge_policy| M[DET: Off|Classify|Always atom]
  M --> ART

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,HY,D,F,ORPH,WT,T,P,PR,M det
```

## Notes

- **Named tasks = idempotency.** `open_pr` z `persist_result` — retry flow run nie otwiera drugiego PR.
- **Retry = ten task.** `retries=2` na infra; semantyka „napraw testy” = `@flow` woła ponownie `implement` z `failure_log` (budżet N).
- **Fail closed.** Czerwony test + wyczerpany budżet → skip/escalate, nie gruby mózg.
- **Parallelogram = skrypt.** Te same atomy SOUL: claim / worktree / test / git / PR / merge_policy.
- **Handoff.** Leave idle/defer/skip = receipt; yield task-llm = `{failure_log?, attempt, schema}`; yield artifacts-pr = `{pr_url?, policy, checks}`.
