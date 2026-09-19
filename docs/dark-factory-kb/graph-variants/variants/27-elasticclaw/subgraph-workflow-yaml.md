# Subgraph: workflow-yaml

**Theme:** Workflow YAML = program control plane; load + publish przed jakimkolwiek sandboxem.  
**Mode mix:** DET only. Zero tokenów na spine.

## Flow

```mermaid
flowchart TD
  A([enter: issue event / manual trigger]) --> B[DET: match trigger filters]
  B --> C{labels team project state?}
  C -->|no match| Z([leave: ignore])
  C -->|match| D[DET: load .elasticclaw/workflows/*.yaml]
  D --> E[DET: schema_version + stages validate]
  E --> F{known fields only?}
  F -->|unknown / LLM-in-route| BAD[DET: reject fail-closed]
  BAD --> ESC([leave: escalate])
  F -->|ok| G[DET: bind workspace + concurrency_group]
  G --> H[DET: workflow push / run_id]
  H --> I[(published stages AST + run_id)]
  I --> J([yield: hub-det-stages])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  classDef bad fill:#3a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,E,G,H det
  class I store
  class BAD bad
```

## Notes

- **YAML-is-code.** Topologia żyje w `.elasticclaw/workflows/` wersjonowanym w PR. `elasticclaw workflow push` publikuje do workspace — zmiana lane’u = diff, nie chat-loop.
- **Trigger = filtr fabryki.** Linear `status_changed` / GH `issue_labeled` / Shortcut / webhook + `labels` / `exclude_labels` / team / project. Brak match → ignore (nie „agent wybiera kolejkę”).
- **Allowed surface (klepacz subset):** `trigger`, `stages[]` (`id`, `entry`, `triggers`, `on_enter`, `gate`, `plan_gate`, `skip_if`, `terminal`), `concurrency_group`, `provider`, `secret_refs`. Wyrażenie „next stage = model decides” → reject.
- **One run per ticket.** `concurrency_group` + occupancy zanim yield; nie fan-out katalogu Issues w środku YAML.
- **Handoff contract.** Yield hub-det-stages = `{workflow_ast, run_id, workspace_id, entry_stage, vars}`.
