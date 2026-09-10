# Macierz porównawcza

| System | Issue→PR | Auto-merge | Multi-agent | Executor | Limbo risk | Dark score* |
|--------|----------|------------|-------------|----------|------------|-------------|
| godark | Tak | Tak / escalate | 3 role | CLI+Docker | `needs-human-review` | Wysoki |
| gp-foundry | Tak | merge_gate | Crew + cron | GitHub Actions | `needs-human` po nudge | Wysoki |
| 0-sayed DF | Tak | merge-gate | AO workers | Orchestrator | Bootstrap ludzki | Wysoki |
| Factory Missions | Cel/plan→PR | Zależnie | Droids | Factory platform | Intervene UI | Śr–wys |
| Devin | Tak | Opcjonalnie | Child agents | Devbox cloud | Human review norm | Średni |
| Cursor Cloud | Task→PR | Nie domyślnie | 1 agent | Cursor VM | Usage wall | Śr (worker) |
| Copilot agent | Tak | Branch rules | 1 | GitHub | Review | Śr |
| OpenHands | Task | Nie | Delegacje | SDK/server | n/a | Niski (platforma) |
| SWE-agent | Bench/issue | Nie | 1 | Lokalnie | n/a | Niski (research) |

\*Dark score = jak blisko lights-out mill bez ciągłego pilota (subiektywne).
