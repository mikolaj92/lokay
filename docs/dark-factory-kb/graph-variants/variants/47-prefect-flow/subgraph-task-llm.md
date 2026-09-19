# Subgraph: task-llm

**Theme:** LLM siedzi **tylko** w `@task` `plan_issue` / `implement` — wypełnia SO; nie routuje `@flow`.  
**Mode mix:** AGENT leaf only (plan|impl). Brak LLM-review w tym wariancie jako sędziego.

## Flow

```mermaid
flowchart TD
  A([enter: LLM @task scheduled]) --> B[DET: load prompt_ref + schema + ticket_ctx]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{leaf kind?}
  D -->|plan_issue| P[AGENT SO: plan files / tests / stop_if]
  D -->|implement| I[AGENT SO: edit in worktree]
  D -->|other| FORBID[DET: reject — only plan/impl allowed]
  P --> E{ok structured?}
  I --> E
  FORBID --> OUT
  E -->|ok:true| OK[DET: return artifact → persist]
  E -->|ok:false| NO[DET: return fail reason enum]
  OK --> OUT([leave: resume @flow])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: fail task]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,OK,NO,KILL,FORBID det
  class P,I agent
```

## Notes

- **Only plan + implement.** Invariant wariantu 47: żadnego LLM `@task` na review/merge/routing. Review po PR = człowiek / osobna rola.
- **Not a router.** Model nie woła Deployment, nie przestawia labeli, nie decyduje o merge, nie wybiera „co dalej”.
- **One task, one leaf.** `plan_issue` i `implement` = osobne `@task` (osobne persist). Repair = ponowne `implement` z `failure_log`, nie nowy „brain”.
- **Structured output.** `ok:true` + artefakt (plan.md / diff receipt) albo `ok:false` + reason enum.
- **Infra retry ≠ blind re-prompt.** Prefect `retries=` na crash; naprawa testów to decyzja `@flow` + nowy call `implement`.
- **Meat ≡ AI.** Ten sam schema seat.
- **Handoff.** Leave = `{task_name, ok, artifact_ref, reason?, usage}` → `@flow` idzie DET ścieżką; opcjonalnie yield artifacts-pr dla planu.
