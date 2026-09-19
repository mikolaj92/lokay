# 25 — jnurre TDD FSM (sandbox-pal)

**Persona:** `jnurre-tdd-fsm compose` — wierność [jnurre64/sandbox-pal-action](https://github.com/jnurre64/sandbox-pal-action): **label-driven GHA FSM** `triage → plan → TDD → review → PR` (+ revision / post-merge cleanup). Agenty = liście (Claude Code / Codex); routing = etykiety + dispatch.

**Approach:** `compose_jnurre_tdd`. Stan maszyny żyje w etykietach `agent*` na issue/PR. Executor = GitHub Actions na self-hosted runnerze + skrypty `.sandbox-pal-dispatch/` (standalone lub reusable `@v1`). Bez SaaS orkiestratora.

## Design notes

- **Label = impuls i stan.** `agent` / `agent:implement` / `agent:plan-approved` / `agent:pr-open` / `agent:revision` / `agent:needs-info` / `agent:review-unresolved`. GHA `on: issues.labeled` (i review/merge) przesuwa FSM — agent **nie** woła `gh label` sam z siebie.
- **triage → plan HITL.** Triage + plan comment; brak approve → `agent:needs-info`. Approve = etykieta `agent:plan-approved` (człowiek lub wąska policy), nie ten sam model.
- **TDD przed PR.** Implement w fresh worktree; bramka DET `AGENT_TEST_COMMAND` musi być zielona zanim dispatch otworzy PR. Czerwone testy ≠ `agent:pr-open`.
- **Adversarial review.** Osobny profil/liść (nie implementer). Werdykt enum → approve / revision / unresolved. Circuit breaker na cap revision.
- **Coder ceiling = PR.** Sufit = `agent:pr-open`. Merge zostaje przy człowieku (domyślnie MergePolicy **Off**); changes requested → `agent:revision` → z powrotem do PR.
- **Post-merge cleanup.** Po merge: sprzątanie worktree / etykiet / runner artifacts — DET, nie „agent się domyśli”.
- **DET majority.** Parse label, mutex stage, worktree, test gate, push, open PR, flip label, cleanup — skrypt/GHA. AGENT tylko: triage/plan SO, TDD implement SO, adversarial review SO, revision SO.
- **Meat ≡ AI.** To samo siedzenie w slocie; graf się nie zmienia.
- **NOT L5.** Zdejmujemy klepanie issue→plan→test→PR→review ping. Nie lights-out bank.
- **Próg wejścia (conf 84):** self-hosted + bot PAT; nie Marketplace one-click — za to najczystszy agent-pipeline label-FSM z fali E.

## Top-level flowchart

```mermaid
flowchart TD
  START([issues:labeled agent* / PR review|merge]) --> DISP[subgraph: label-dispatch]
  DISP -->|illegal / unknown| DROP([ignore + receipt])
  DISP -->|triage / plan stages| TP[subgraph: triage-plan]
  DISP -->|implement / TDD| TDD[subgraph: tdd-implement]
  DISP -->|review / revision| ADV[subgraph: adversarial-review]
  DISP -->|pr-open / merged| PRC[subgraph: pr-cleanup]

  TP -->|needs-info| ESC([agent:needs-info])
  TP -->|plan-approved| ADV1[DET: label → agent:implement]
  ADV1 --> TDD
  TDD -->|tests red / fail SO| ESC
  TDD -->|green + branch| ADV2[DET: handoff review]
  ADV2 --> ADV
  ADV -->|OK| ADV3[DET: label → agent:pr-open]
  ADV -->|cap| UNRES([agent:review-unresolved])
  ADV -->|changes + budget| REV[DET: label → agent:revision]
  REV --> TDD
  ADV3 --> PRC
  PRC -->|changes requested| REV2[DET: agent:revision]
  REV2 --> TDD
  PRC -->|merged| CLEAN([post-merge cleanup])
  PRC -->|hold Off| HOLD([PR open — human merge])

  classDef sub fill:#1a2a3a,stroke:#3a7ab8,color:#e8f2ff
  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class DISP,TP,TDD,ADV,PRC sub
  class ADV1,ADV2,ADV3,REV,REV2 det
  class DROP,ESC,UNRES,HOLD stop
  class CLEAN ok
```

**DET vs AGENT at a glance**

| Warstwa | Mode | Kto | Uwaga |
|---------|------|-----|-------|
| `issues:labeled` / PR review|merge | DET | GHA | jedyny start / re-drive |
| Flip etykiety `agent*` | DET | sandbox-pal dispatch | agent nie flipuje |
| Triage + plan comment | AGENT SO | liść | po ok → czekaj HITL |
| `agent:plan-approved` | HITL / policy | człowiek | nie autor planu |
| Implement TDD + worktree | AGENT SO + DET gate | liść + atom | `AGENT_TEST_COMMAND` |
| Open PR / label `agent:pr-open` | DET | script | po green + review OK |
| Adversarial review / revision | AGENT SO + DET cap | osobny liść | circuit breaker |
| Merge Off\|Classify\|Always | DET / human | policy | default Off |
| Post-merge cleanup | DET | GHA | worktree + labels |

## Index of subgraphs

| File | Theme | Role in chain |
|------|--------|----------------|
| [subgraph-label-dispatch.md](./subgraph-label-dispatch.md) | tabela `agent*` + mutex + GHA impulse | DET kręgosłup FSM |
| [subgraph-triage-plan.md](./subgraph-triage-plan.md) | triage + plan HITL | AGENT slot; escape `needs-info` |
| [subgraph-tdd-implement.md](./subgraph-tdd-implement.md) | worktree + TDD gate | AGENT kod; DET `AGENT_TEST_COMMAND` |
| [subgraph-adversarial-review.md](./subgraph-adversarial-review.md) | adversarial review + revision cap | AGENT werdykt; DET breaker |
| [subgraph-pr-cleanup.md](./subgraph-pr-cleanup.md) | `agent:pr-open` + revision + cleanup | coder ceiling; merge human |

## Label vocabulary (jnurre native)

| Label | Znaczenie | Kto ustawia |
|-------|-----------|-------------|
| `agent` | start / triage queue | człowiek |
| `agent:implement` | TDD implement slot | GHA po plan-approved |
| `agent:plan-approved` | HITL/policy OK na plan | człowiek / policy |
| `agent:needs-info` | escape z triage/plan | GHA |
| `agent:pr-open` | PR otwarty; czeka merge | GHA po review OK |
| `agent:revision` | changes requested / fix loop | GHA / review event |
| `agent:review-unresolved` | cap adversarial / stranded | GHA circuit breaker |

Mapowanie na `workflow:*` z wariantu `09-label-fsm` jest opcjonalne (aliases w 09); tu **kanon = słownik jnurre**.

## Mapowanie sandbox-pal → klepacz

| sandbox-pal | Klepacz seat |
|-------------|--------------|
| `on: issues.labeled` `agent*` | subgraph-label-dispatch |
| Triage + plan comment | subgraph-triage-plan |
| `agent:plan-approved` HITL | plan gate (DET wait) |
| Worktree + Claude/Codex implement | subgraph-tdd-implement |
| `AGENT_TEST_COMMAND` | DET TDD gate przed PR |
| Adversarial review loop | subgraph-adversarial-review |
| `agent:pr-open` + revision | subgraph-pr-cleanup |
| Post-merge cleanup | DET cleanup w pr-cleanup |
| Agent as label router | **FORBIDDEN** |

## Antyteza (czego tu nie ma)

- Agent wybierający next issue z czatu / unlabeled backlogu
- Agent sam flipujący `agent*` „bo tak wyszło z promptu”
- PR na czerwonym `AGENT_TEST_COMMAND`
- Review = ten sam profil co implement (brak adversarial separation)
- Unbounded revision bez `agent:review-unresolved`
- Merge w liściu implementera / L5 lights-out
