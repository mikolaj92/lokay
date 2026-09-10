# Factory.ai (Droids / Missions / Software Factory)

**Typ:** zamknięty platform (agent-native SDLC)  
**Producent:** Factory  
**Rola:** świadomie „software factory” — sygnały → plan → multi-agent Missions → validate → ship; spektrum autonomii

## Architektura

```
Signals (bugs, Linear/Jira, feedback, requirements)
    → triage / plan (Coordinator / Orchestrator)
    → Context (Autowiki index, memory, skills, MCP)
    → Execution: Droids (code/test/review/docs/knowledge) w sandbox
    → Missions: validation contract → milestones → features
         Worker (TDD: tests first) → Scrutiny validator → User-testing validator
         → fix features loop aż milestone pass
    → Code Review / Droid Shield / policy
    → PR / deploy hooks
    → monitoring → nowe signals
```

### Missions (rdzeń długiego autonomicznego runu)
1. Orchestrator definiuje **validation contract** (behavioral assertions) **zanim** features.
2. Features claim assertions; grupowane w milestones.
3. Programmatic runner spawnuje **worker per feature** ze **świeżym kontekstem**; TDD.
4. **Scrutiny validators** — jakość trajektorii + knowledge updates do shared state.
5. **User-testing validators** — black-box vs contract.
6. Orchestrator tworzy fix features na luki → re-validate.

Źródło: [factory.ai/news/missions-architecture](https://factory.ai/news/missions-architecture), [docs.factory.ai Missions](https://docs.factory.ai/cli/features/missions)

### Spektrum autonomii (Factory 2.0)
- Simple Droid / skills — krótkie, mierzalne taski
- Automations — recurring shared objective + memory
- Droid Computers — remote/persistent long-running
- Missions — multi-agent hours/days

Źródło: [factory.ai/news/software-factory](https://factory.ai/news/software-factory)

### Warstwy „software factory architecture”
Specification → context resolution → execution → review/policy → deploy/monitor.  
Code Review scoring vs policy; LLM safety; secret detection (Droid Shield).

## Human gates
| Gate | Opis |
|------|------|
| Mission plan collaborate | Conversation → features/milestones; approve przed Mission Control |
| Mission Control intervene | Monitor + ręczne wejście |
| Code Review / merge | Policy + człowiek |
| Agent Readiness | Organizacja decyduje poziom autonomii per proces |

## Eval / CI
- Dwupoziomowe TDD: feature tests + mission-level behavioral contract.
- Adversarial validators (scrutiny + user-testing).
- Droid CLI headless w CI (`droid exec` / mission paths w docs).
- Shared agent core: security finding informuje review, incident ↔ PR.

## Multi-agent vs single
**Explicit multi-agent:** coordinator + specialized droids; Missions = orchestrator/workers/validators. Najbliższy marketingowi „software factory” wśród vendorów.

## Failure / retry
- Milestone fail → fix features → re-validate loop.
- Shared state artifacts (contract, feature list, research notes) — nie jeden kontekst LLM.
- Fresh worker context ogranicza contamination.

## Czego NIE automatyzuje
- Ambiguous product decisions bez planu
- Pełny lights-out bez Agent Readiness / policy
- Zastąpienie org process (ticket hygiene nadal krytyczna)

## Open-source vs closed
**Closed** platform. Public blogs + docs/CLI; model-agnostic / BYOK w opisach.

## Kluczowe URL-e
- https://factory.ai/news/software-factory
- https://factory.ai/news/missions-architecture
- https://docs.factory.ai/cli/features/missions
- https://factory.com/articles/what-is-a-software-factory-architecture
