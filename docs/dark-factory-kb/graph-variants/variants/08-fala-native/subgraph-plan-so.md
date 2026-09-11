# Subgraph: plan-so

**Stage cluster:** plan SO  
**Mode:** **jeden** liść LLM (structured output) otoczony cienkimi atomami DET.  
**Handoff in:** worktree ready + issue hard_facts.  
**Handoff out:** plan JSON albo skip (`ok:false`).

## Flow

```mermaid
flowchart TD
  A([enter: worktree + issue]) --> B[ATOM: read_issue_body]
  B -->|ok:false| X([leave: fail])
  B -->|ok| C[ATOM: collect_allowed_paths]
  C -->|ok:false| X
  C -->|ok| D[SO LEAF: plan_issue]
  D -->|ok:false| S([leave: skip — no limbo])
  D -->|ok| E[ATOM: validate_plan_schema]
  E -->|ok:false| S
  E -->|ok| F[ATOM: write_plan_artifact]
  F -->|ok:false| X
  F -->|ok| G([leave: plan ready])

  classDef atom fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef so fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,E,F atom
  class D so
```

## Structured output — `plan_issue`

```json
{
  "ok": true,
  "goal": "...",
  "files": ["..."],
  "test_command": "...",
  "non_goals": ["..."],
  "stop_if": ["auth", "migration"]
}
```

Fail leaf:

```json
{ "ok": false, "reason": "underspecified" }
```

`reason` ∈ `underspecified` | `too_large` | `dangerous` → **skip bez limbo**.

## Atomy wokół liścia

| Atom | Rola |
|------|------|
| `read_issue_body` | DET odczyt; LLM nie „szuka” issue tool-callingiem |
| `collect_allowed_paths` | z szablonu / allowlist repo |
| `validate_plan_schema` | JSON Schema check — nie LLM |
| `write_plan_artifact` | zapis do worktree / reaction store |

## Notes

- **Plan nie pisze kodu produktu.** Tylko artifact pod implement.
- **LLM = liść.** Adapter woła model z fixed prompt + schema; zero pętli tooli w tym węźle.
- **`when=` dalej:** parent może odpalić implement tylko gdy `plan_issue.ok == true` (albo po `validate_plan_schema`).
- **Meat ≡ AI.** Ten sam SO seat.
