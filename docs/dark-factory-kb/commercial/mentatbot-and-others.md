# MentatBot (AbanteAI) + inne OSS/adjacent factory agents

## MentatBot / Mentat (AbanteAI)

**Typ:** closed GitHub-native bot (+ archived OSS CLI)  
**Producent:** AbanteAI — https://mentat.ai

### Architektura (obserwowalna)
```
Install Mentat GitHub App → repo settings
    → Issue + @MentatBot → branch/commit → PR
    → Auto review nowych PR (konfigurowalne)
    → Mentat Scripts (repo-specific format/test helpers)
    → Credits billing
```

- Setup issue checklist: Reviews, Pull Requests, Mentat Scripts, payment ([template](https://github.com/AbanteAI/mentat-template-js/issues/1)).
- Model routing: wybór spośród OpenAI/Anthropic itd. (vendor claims).
- **Stary Mentat CLI** (Apache-2.0) → [archived](https://github.com/AbanteAI/archive-old-cli-mentat); nazwa Mentat = teraz bot.

### Human gates
Tag `@MentatBot`; PR review/merge; credits; script generation request.

### Multi-agent
Fleet of agents na dashboardzie agents page — parallel capacity, nie Missions-style validators.

### Open vs closed
Hosted MentatBot **closed**; historyczny CLI OSS archived.

### URL-e
- https://mentat.ai
- https://github.com/AbanteAI/mentat-template-js
- https://github.com/AbanteAI/archive-old-cli-mentat

---

## OpenHands (All Hands / OpenHands)

**Typ:** **open-source** MIT — self-host / cloud / enterprise  
**Rola:** pełna platforma agentowa (GUI + app server + sandbox + agent-server + SDK + event store + MCP + skills)

### Architektura (produktowa)
```
App server (FastAPI) — NIE wykonuje tooli bezpośrednio
    → tworzy sandbox + StartConversationRequest
    → agent-server + SDK wewnątrz sandbox (ReAct-style loop)
    → event-sourced conversation / Agent Canvas UI
    → opcjonalnie VPC / air-gapped
```

Ważna granica bezpieczeństwa: **niebezpieczne wykonanie tylko w sandbox**; app server trzyma metadata/credentials boundary.

Źródła: [openhands.dev OSS agents](https://www.openhands.dev/blog/open-source-ai-coding-agents), [architecture analysis](https://martianlee.github.io/posts/2026-05-17-openhands-architecture)

### Human gates
HITL collaboration; deploy mode; model provider choice.

### vs commercial factories
Najbliższy **self-hosted odpowiednik** Devin/Cursor cloud pod względem izolacji runtime; Ty operujesz Temporal-like reliability we własnym stacku.

---

## Aider

**Typ:** OSS Apache-2.0 — terminal pair programmer  
**Mechanizm fabryczny:** git-native atomic commits; map-reduce / architect modes; **nie** cloud issue→PR SaaS.  
Użyteczny jako **local worker** w większej fabryce (CI job woła `aider`).

URL: https://aider.chat / Paul Gauthier repos

---

## Goose (Block) / Cline / Continue

Skrót dla porównania osi (z przeglądów 2026):
| Tool | Loop | Sandbox | Factory fit |
|------|------|---------|-------------|
| Goose | MCP-first | zależy od setup | automation recipes |
| Cline / Continue | IDE agent | często same-process | interactive, nie lights-out |
| OpenHands | ReAct + platform | Docker/chroot | self-hosted factory core |

Źródło porównawcze: [runlocalai agent execution systems](https://www.runlocalai.co/systems/agent-execution-systems)

---

## Kiedy brać „others” zamiast big SaaS
- Wymóg VPC/air-gap → OpenHands / self-host Sweep  
- Git-commit discipline lokalnie → Aider  
- Tani GitHub chore bot → MentatBot / Sweep (jeśli aktywne)  
- Pełny managed env + artifacts → Cursor / Devin / Jules  
