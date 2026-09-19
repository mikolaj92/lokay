# Subgraph: optional-plan

**Theme:** maleńki AGENT plan **dopiero po** script picku.  
**Mode mix:** jeden wąski liść SO; wejście/wyjście DET.  
**Default:** **skip** — ticket jasny → prosto do implement-ship.

## Flow

```mermaid
flowchart TD
  A([enter: frozen issue + branch]) --> B{flag: run_tiny_plan?}
  B -->|no / default| S([leave: skip → implement])
  B -->|yes| C[DET: pack issue hard facts for SO]
  C --> D[AGENT SO: tiny plan]
  D --> E{ok?}
  E -->|ok:false underspecified/too_large/dangerous| F([leave: idle — do not invent])
  E -->|ok:true| G[DET: attach plan.json to cell]
  G --> H([leave: plan → implement])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class C,G det
  class D agent
```

## Tiny plan SO contract

**ok:true**

```json
{
  "ok": true,
  "goal": "…",
  "files": ["…"],
  "test_command": "…",
  "non_goals": ["…"],
  "stop_if": ["…"]
}
```

**ok:false** — enum `reason`: `underspecified` | `too_large` | `dangerous`

Plan **nie** może:

- zmienić wybranego `issue_id`
- dodać drugiego ticketa
- otworzyć nowego picku / listy issues
- routować następnego węzła grafu

## Notes

- **After pick only.** Wywołanie przed script-intake jest niedozwolone — złamałoby invariant „agent never chooses work”.
- **Optional = skip by default.** Script-first pragmatic: nie planujemy dla sportu.
- **Tiny.** Goal + files + stop_if. Nie epic breakdown, nie multi-PR roadmap.
- **Fail → idle, nie enrich.** `underspecified` kończy przebieg; człowiek poprawia issue / label. Plan leaf nie dopisuje acceptance.
- **Meat ≡ AI.** Ten sam schema liść — człowiek-planista albo model.
- **Handoff:** `{issue, branch, plan?}` — `plan` optional field.
