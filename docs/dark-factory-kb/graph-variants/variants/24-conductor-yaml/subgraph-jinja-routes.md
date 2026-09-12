# Subgraph: jinja-routes

**Theme:** Orkiestracja = wyrażenia Jinja; **0 tokenów**; first matching condition wins.  
**Mode mix:** DET only. Model nie wybiera następnego kroku.

## Flow

```mermaid
flowchart TD
  A([enter: current step / vars]) --> B{step kind?}
  B -->|route| C[DET: eval Jinja conditions in order]
  C --> D{first match?}
  D -->|needs_code / plan_done| AGENT([yield: agent-leaf])
  D -->|run_tests / git / open_pr| SCRIPT([yield: script-hitl])
  D -->|clarify / merge_off| HITL([yield: script-hitl human_gate])
  D -->|success / failed| TERM([yield: script-hitl terminate])
  D -->|no match| IDLE([leave: idle / escalate])
  B -->|agent| AGENT
  B -->|script / set / mcp / human_gate / terminate| SCRIPT
  AGENT -->|session result → set vars| A
  SCRIPT -->|exit code / set vars| A

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class C det
  class IDLE stop
```

## Notes

- **0-token orchestration.** Eval Jinja na `vars` (wyniki `script`, SO z liści, `set`) — bez promptu, bez tool-call routera.
- **First match wins.** Kolejność warunków w YAML = priorytet (np. `budget_exhausted` przed `retry_fix` przed `tests_ok`).
- **Klepacz diamonds (przykłady):** `occupancy_free`, `plan_ok`, `tests_ok`, `attempt < N`, `policy == 'Always'`, `needs_clarify`.
- **Not a chat FSM.** Brak „LLM, co dalej?”. Po liściu agent wynik ląduje w `set` / vars i wraca do tego podgrafu.
- **Handoff contract.** Yield agent-leaf = `{step_id, agent_spec, prompt_ref, schema, vars_slice, attempt}`; yield script-hitl = `{step_id, kind, cmd_or_gate, vars}`.
