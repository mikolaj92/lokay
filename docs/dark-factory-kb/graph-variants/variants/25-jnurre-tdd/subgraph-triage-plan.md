# Subgraph: triage-plan

**Theme:** triage issue + plan comment — agent wypełnia treść; approve to etykieta HITL `agent:plan-approved`.  
**Mode mix:** DET claim/flip/wait; AGENT SO triage + plan.

## Flow

```mermaid
flowchart TD
  A([enter: label agent / triage]) --> B[DET: claim issue K=1 + lock]
  B --> C{claim ok?}
  C -->|occupied / defer| Z0([leave: defer])
  C -->|ok| D[AGENT SO: triage — scope / risks / ask-or-stop]
  D --> E{triage ok?}
  E -->|needs human / unclear| F[DET: label → agent:needs-info]
  F --> Z1([leave: escape])
  E -->|ok| G[AGENT SO: write plan comment schema]
  G --> H{SO ok?}
  H -->|ok:false| F
  H -->|ok| I[DET: wait for agent:plan-approved]
  I --> J{approved?}
  J -->|timeout / reject| F
  J -->|yes| K([leave: advance agent:implement])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,I det
  class D,G agent
  class Z0,Z1 bad
```

## Notes

- **Slot ≠ router.** Triage SO zwraca `{ok, clarity, risks[], ask_or_stop?}`. DET mapuje `ask_or_stop` → `agent:needs-info` — agent nie wybiera kolejnego joba.
- **Plan comment = artefakt.** Schema w stylu sandbox-pal: Outcome / Steps / Files / Test command hint / Risks / Ask-or-stop. Pin lub oznaczony komentarz.
- **HITL label.** `agent:plan-approved` dokłada człowiek (lub wąska policy DET) — **nie** ten sam model, który pisał plan.
- **Fail closed.** Brak planu / `ok:false` / timeout approve → `agent:needs-info`, nie ciche „spróbuj innego modelu”.
- **Fast path (opc.).** Bardzo mały ticket: triage może zwrócić `lane=build`; DET i tak wymaga jawnego `plan-approved` albo osobnej policy „skip plan” — default = wymagaj approve (wierność jnurre).
- **Handoff:** `{issue_id, plan_ref}` → label-dispatch advance → TDD.
