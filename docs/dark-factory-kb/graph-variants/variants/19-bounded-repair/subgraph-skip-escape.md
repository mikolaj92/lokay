# Subgraph: skip-escape

**Theme:** po wyczerpaniu N (lub blocked intake) → **skip z receipt**, opcjonalny HITL ping. **Żadnych limbo stamps.**  
**Mode mix:** 100% DET (+ HITL ping). Escape hatch całego wariantu 19.

## Flow

```mermaid
flowchart TD
  A([enter: none / blocked / exhausted / reject]) --> B[DET: normalize reason enum]
  B --> C[DET: write receipt JSON]
  C --> D{detach labels?}
  D -->|yes — default| E[DET: remove ready-for-agent claim only]
  D -->|keep for human retry| E2[DET: leave labels untouched]
  E --> F[DET: annotate issue/PR with receipt link/body]
  E2 --> F
  F --> G{needs human eyes?}
  G -->|reject / high_risk / merge_blocked / pr_repair_exhausted| H[HITL: ping once]
  G -->|idle none / underspecified / local_test_red_exhausted| I[DET: stop quiet]
  H --> J([leave: stop — human owns, no limbo])
  I --> K([leave: stop — clean skip, no limbo])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,E2,F,I det
  class H human
  class J,K bad
```

## Reason enum (closed) — limbo **never**

| reason | Typical source | Default exit | Limbo stamp? |
|--------|----------------|--------------|--------------|
| `idle_none` | intake: brak labeled | quiet stop | **never** |
| `underspecified` | intake | quiet stop | **never** |
| `dirty_worktree` | intake | quiet stop | **never** |
| `implement_fail` | intake SO | quiet stop | **never** |
| `local_test_red_exhausted` | repair-code N | quiet stop + receipt | **never** |
| `push_fail` / `pr_open_fail` | repair-code | quiet stop | **never** |
| `ci_red` / `ci_timeout` | pr-repair | stop + annotate PR | **never** |
| `review_reject` | pr-repair | HITL ping | **never** |
| `pr_repair_exhausted` | pr-repair N | HITL ping; PR left open | **never** |
| `merge_blocked` | pr-repair policy | HITL ping | **never** |
| `high_risk` | classify gate | HITL ping | **never** |

## Receipt shape

```json
{
  "outcome": "skipped",
  "reason": "pr_repair_exhausted",
  "issue_id": 42,
  "pr_url": "https://github.com/org/repo/pull/7",
  "repair_code_used": 1,
  "pr_repair_used": 2,
  "n_repair_code": 2,
  "n_pr_repair": 2,
  "ts": "2026-09-11T09:51:00Z",
  "next": "human",
  "limbo_label": null
}
```

## Notes

- **Skip ≠ limbo.** Limbo stamp odkłada wstyd na tablicy. Tu: audytowalny receipt + stop. Człowiek czyta reason, nie zgaduje z etykiety.
- **Zakazane labele.** `ai:deferred`, `ai:limbo`, `needs-human-maybe`, `workflow:limbo`, `waiting-forever` — nielegalne w tym wariancie. Jedyny „human” sygnał = HITL ping + opcjonalnie istniejący `workflow:needs-human` **tylko** gdy policy to przewiduje jako jawny hold — nadal nie limbo.
- **Detach claim, nie stamp.** Default: zdejmij claim/`ready-for-agent` occupancy, żeby inny worker nie gnił w pętli. Nie doklejaj „deferred”.
- **PR left open przy exhausted pr_repair.** Diff i review comments zostają — to artefakt dla człowieka, nie stan „agent jeszcze wróci”.
- **Jeden ping HITL.** Bez nudge-loop. Pessimista nie spamuje.
- **Top-level łączy tu wszystkie `none` / `blocked` / `exhausted` / `reject`.** Bez tego podgrafu bounded N kończy się w powietrzu.
- **Handoff.** `{skipped:true, receipt}` | `{human_hold:true, receipt}` — nigdy `{label: "limbo"}`.
