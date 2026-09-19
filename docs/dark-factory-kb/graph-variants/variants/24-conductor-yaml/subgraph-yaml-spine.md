# Subgraph: yaml-spine

**Theme:** Workflow YAML = program; load + validate przed jakimkolwiek LLM.  
**Mode mix:** DET only. Zero tokenów na spine.

## Flow

```mermaid
flowchart TD
  A([enter: ready-for-agent / conductor run]) --> B[DET: load workflow.yaml]
  B --> C[DET: schema check step types]
  C --> D{known types only?}
  D -->|no unknown| E[DET: bind inputs ticket_id K=1]
  D -->|unknown / LLM-in-route| BAD[DET: reject fail-closed]
  BAD --> ESC([leave: escalate])
  E --> F[DET: init run state set vars]
  F --> G[(workflow AST + run_id)]
  G --> H([yield: jinja-routes])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  classDef bad fill:#3a1a1a,stroke:#a05050,color:#ffe8e8
  class B,C,E,F det
  class G store
  class BAD bad
```

## Notes

- **YAML-is-code.** Topologia żyje w pliku wersjonowanym w PR. Zmiana lane’u = diff YAML, nie „agent wymyśla pipeline”.
- **Allowed step types (klepacz subset):** `agent`, `script`, `set`, `mcp`, `route`, `human_gate`, `terminate` (+ opcjonalnie `parallel` / `for_each` / sub-workflow). Wszystko inne → reject.
- **Forbid at load time:** wyrażenie route z wywołaniem modelu; `type: agent` jako jedyny krok bez sąsiadów `script`/`route`; brak `terminate`.
- **One run per ticket.** `set` ticket_id + occupancy check zanim yield do routes; nie fan-out katalogu w środku YAML.
- **Handoff contract.** Yield jinja-routes = `{workflow_ast, run_id, vars, entry_step}`.
