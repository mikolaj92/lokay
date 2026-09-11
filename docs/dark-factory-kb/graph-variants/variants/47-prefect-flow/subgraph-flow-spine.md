# Subgraph: flow-spine

**Theme:** Prefect Deployment (labeled issue) → `@flow` = deterministyczny szkielet; task results = źródło prawdy.  
**Mode mix:** DET only. Zero LLM w ciele `@flow` (poza wnętrzem LLM `@task`).

## Flow

```mermaid
flowchart TD
  A([enter: issues.labeled ready-for-agent]) --> B[DET: Automation → Deployment]
  B --> C[DET: start flow run params.issue_id]
  C --> D[DET: @flow klepacz_ticket_to_pr bind]
  D --> E[(task result store / flow-run state)]
  E --> F[DET: next @task in fixed order]
  F --> G{task kind?}
  G -->|CODE @task| DET([yield: task-det])
  G -->|LLM plan/impl| LLM([yield: task-llm])
  G -->|artifacts / PR / pause| ART([yield: artifacts-pr])
  G -->|terminal ok| DONE([leave: done])
  G -->|terminal fail| ESC([leave: escalate])
  DET -->|result persisted| E
  LLM -->|result persisted| E
  ART -->|resume / merge state| E

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,D,F det
  class E store
```

## Notes

- **Label = start, nie chat-pick.** Automation na `ready-for-agent` tworzy flow run. Agent nie skanuje boardu w `@flow`.
- **Flow body = czysta kontrola.** Kolejność: hydrate → claim/worktree → plan → implement → tests → (bounded repair) → open_pr → artifacts → pause → merge_policy.
- **Replay mental model.** Po restarcie workera Prefect wznawia od nieukończonych tasków; `persist_result` pomija udane.
- **Orkiestrator nie myśli.** `next @task` = stała kolejność klepacza + diamenty budżetu — nie tool-calling router.
- **One flow run per ticket.** K=1 egzekwowane w DET claim/worktree.
- **Handoff.** Yield task-det = `{task_name, issue_id, idempotency_key, input_ref}`; yield task-llm = `{task_name: plan|implement, schema, ticket_ctx, attempt}`; yield artifacts-pr = `{pr_ref, artifact_keys, policy}`.
