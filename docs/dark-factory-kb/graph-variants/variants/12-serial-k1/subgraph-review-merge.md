# Subgraph: review-merge

**Theme:** CI DET → critical review SO → merge policy DET → **zwolnienie slotu K=1**.  
**Mode mix:** DET CI/policy + AGENT review (osobna rola).  
**Handoff in:** exactly one PR open for the ticket.  
**Handoff out:** merged | left open (Off/high) | changes → back to **same** worktree (no new claim).

## Flow

```mermaid
flowchart TD
  A([enter: one PR open]) --> B[DET: wait CI checks]
  B -->|red| H[DET: hold PR — no merge]
  H --> Back{human / fix?}
  Back -->|fix on same branch| Z([leave: changes → same worktree])
  Back -->|abandon| U[DET: unlock slot + teardown]
  U --> Idle([leave: idle — K=1 free])
  B -->|green| C[AGENT SO: pr_review]
  C -->|reject / risk high| H2[DET: hold — never Always]
  H2 --> Back
  C -->|changes| Z
  C -->|approve| D{MergePolicy?}
  D -->|Off| Hold([leave: PR open — człowiek; unlock after human outcome])
  D -->|Classify| E{risk low?}
  E -->|no| Hold
  E -->|yes| F[DET: merge + close issue]
  D -->|Always| F
  F --> G[DET: teardown worktree + release claim lock]
  G --> Done([leave: done — catalog may open next tick])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,H,U,H2,E,F,G det
  class C agent
  class Idle,Hold,Z stop
  class Done ok
```

## AGENT leaf

**`pr_review`** → `{verdict: approve|changes|reject, reasons[], risk: low|high}`  
- `reject` / `risk:high` → **nigdy** Always-merge  
- `reasons[]` nosi niewygodne pytania QA (bez osobnego QA-strategy AGENT)

## DET policy

| Knob | Zachowanie |
|------|------------|
| **Off** *(default)* | PR zostaje otwarty; człowiek merguje; slot zwalniany po human outcome / explicit unlock |
| **Classify** | auto-merge tylko `approve` + `risk:low` + CI green |
| **Always** | merge gdy CI green **i** verdict ≠ reject **i** risk ≠ high |

## Notes

- **Changes → ten sam worktree.** Nie nowy claim, nie nowy path, nie siew katalogu. K=1 trwa do done/abandon.
- **Slot free dopiero na exit.** `release claim lock` + teardown po merge/abandon/human Off outcome — dopiero wtedy kolejny tick może `pick_one_k1`.
- **Reviewer ≠ implementer.** Osobna rola SO; brak write do kodu w tym liściu (opcjonalnie enforced allowlist).
- **Merge jest DET.** Gałka Off\|Classify\|Always — nie prompt „czy zmergować”.
- **NOT L5.** Off default trzyma człowieka przy merge gdy polityka tak każe; graf zdejmuje klepanie, nie odpowiedzialność.
