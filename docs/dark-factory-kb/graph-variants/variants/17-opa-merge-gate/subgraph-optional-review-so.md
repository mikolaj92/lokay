# Subgraph: optional-review-so

**Theme:** opcjonalny krytyczny review AGENT SO — **doradczy**.  
**Mode mix:** AGENT SO + DET wait CI. **Zakaz:** ten podgraf nie merguje i nie wystawia `allow`.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: fetch CI status]
  B --> C{review SO enabled?}
  C -->|no — skip| S([leave: advisory=null, ci_facts])
  C -->|yes| D{CI green enough to review?}
  D -->|hard red| E([leave: advisory skipped, ci=red])
  D -->|yes / soft| F[AGENT SO: critical review]
  F --> G[DET: attach SO as PR comment / artifact]
  G --> H([leave: advisory SO + ci_facts])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef warn fill:#3a2a1a,stroke:#c4893a,color:#fff6e8,stroke-dasharray: 5 5
  class B,G det
  class F agent
  class C warn
```

## Structured output (kontrakt)

```json
{
  "verdict": "approve|changes|reject",
  "reasons": ["..."],
  "risk": "low|medium|high",
  "questions": ["niewygodne pytanie QA..."]
}
```

## Notes

- **Cynical axiom.** `verdict: approve` od LLM **nie** otwiera merge. To pole w JSON dla OPA — jeśli policy w ogóle je czyta.
- **Optional.** Gałka off = zero tokenów na „sędziego”. Policy i tak może wymagać człowieka (hold).
- **Osobna rola.** Nie ten sam seat co implement (meat lub AI).
- **reasons[] = QA strategy.** Niewygodne pytania tu, nie osobny teatr „strategia AGENT”.
- **CI red:** nie proś modelu o override. Zostaw fakty; OPA i tak fail-closed.
- **Handoff:** `{advisory: SO|null, ci_status, checks[]}` → opa-merge-gate. Żadnego `merge=true` z tego węzła.
