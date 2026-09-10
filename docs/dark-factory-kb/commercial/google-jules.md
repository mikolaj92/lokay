# Google Jules

**Typ:** zamknięty (Google Labs / Google Cloud)  
**Producent:** Google  
**Rola:** async coding agent — queue session → plan (±approve) → VM execute → PR

## Architektura

```
Trigger (jules.google UI / CLI / API / GitHub label|mention)
    → Session w task pool (QUEUED)
    → PLANNING → [AWAITING_PLAN_APPROVAL?] → IN_PROGRESS
    → Ephemeral Google Cloud VM + Environment Snapshot (deps)
    → clone repo → edit → bash/tests → artifacts
    → SessionOutput.PullRequest (jeśli automationMode=AUTO_CREATE_PR)
    → COMPLETED | FAILED
    → człowiek: review / merge
```

### API primitives (oficjalne typy)
- **Source** — podłączone repo (GitHub app)
- **Session** — jednostka pracy (`prompt`, `requirePlanApproval`, `automationMode`, `sourceContext`)
- **Activity** — eventy: PlanGenerated, PlanApproved, ProgressUpdated, SessionCompleted/Failed, ChangeSet/GitPatch, BashOutput, Media
- **AutomationMode:** `AUTO_CREATE_PR` vs unspecified (bez auto-PR)
- **SessionState:** QUEUED → PLANNING → AWAITING_PLAN_APPROVAL → AWAITING_USER_FEEDBACK → IN_PROGRESS → PAUSED / FAILED / COMPLETED

Źródło: [jules.google/docs/api/reference/types](https://jules.google/docs/api/reference/types/)

### Model / execution notes
- Blog I/O 2025: Gemini 2.5 Pro; third-party reporty: Pro do planowania, Flash do lżejszych kroków; GA Aug 2025.
- Parallel sessions na osobnych VM.
- Environment Snapshot przyspiesza setup zależności.

Źródło produktu: [blog.google Jules public beta](https://blog.google/innovation-and-ai/models-and-research/google-labs/jules/)

## Human gates
| Gate | Opis |
|------|------|
| `requirePlanApproval` | Plan musi być zatwierdzony przed exec |
| Steerability | Edycja planu przed/w trakcie/po |
| AWAITING_USER_FEEDBACK | Agent zatrzymuje się na input |
| PR merge | Człowiek |
| AUTO_CREATE_PR | Opcjonalne; nie = merge |

## Eval / CI
- BashOutput z exitCode w activities — agent widzi wynik komend/testów w VM.
- Critique/testing role — opisy third-party; oficjalne API eksponuje artifacts, nie osobne nazwy ról.
- Po PR: standardowe GitHub CI.

## Multi-agent vs single
- **Session = primary unit** (single orchestrated run).
- External writeupy opisują planner/execution/critique/testing — **nie w pełni w public API**.
- Parallelizm = wiele Session, nie jeden shared orchestrator jak Factory Missions.

## Failure / retry
- `FAILED` + SessionFailed reason.
- `PAUSED` / user feedback.
- Nowa session lub SendMessage do kontynuacji.
- Teardown VM po zakończeniu.

## Czego NIE automatyzuje
- Merge / deploy
- Gwarantowany multi-day resumable orchestrator z hash-checkpointami (por. Devin workflows)
- Trenowanie na private code (private by default — deklaracja Google)

## Open-source vs closed
**Closed.** Public REST API docs + web/CLI; runtime Jules nie OSS.

## Kluczowe URL-e
- https://blog.google/innovation-and-ai/models-and-research/google-labs/jules/
- https://jules.google/docs/api/reference/types/
- https://jules.google/
