# Cursor Cloud Agents (dawniej Background Agents)

**Typ:** zamknięty (Cursor) — agent loop + infrastruktura cloud  
**Producent:** Anysphere / Cursor  
**Rola:** równoległe, długotrwałe agenty w izolowanych VM → build/test/artifacts → PR

## Architektura

```
Trigger (Desktop Cloud / cursor.com/agents / Slack @cursor /
         GitHub|Bitbucket comment @cursor / Linear / iOS / API)
    → Frontend (stateless) tworzy DB entry + Temporal workflow
    → Temporal workers: provision/reuse VM → agent loop
    → VM: clone repo(s), deps, secrets, MCP, hooks, computer use
    → edit → test → artifacts (screenshots/video/logs)
    → push branch + PR handoff
    → człowiek: review / remote desktop / follow-up
```

### Trzy rozłączone stany (lekcja Cursor)
1. **Agent loop** — w Temporal (nie na VM) → retries, hibernacja podów, multi-day runs  
2. **Machine state** — lifecycle VM niezależny (readonly / prewarmed pods)  
3. **Conversation state** — append-only stream; przy retry klient rewinduje partial output  

Źródło: [cursor.com/blog/cloud-agent-lessons](https://cursor.com/blog/cloud-agent-lessons) (Jun 2026)  
Operacyjnie: Temporal Cloud → >50M actions/day, >7M workflows; wewnętrznie **>40% PR** z cloud agents.

### Środowisko = produkt
Konfiguracja: agent-led setup, snapshot, lub Dockerfile via `.cursor/environment.json`. Bez pełnego env jakość spada „cicho” (nie crash). Secrets dashboard, egress allowlist, Tailscale/private connectivity, Self-Hosted Machines.

Docs: [cursor.com/docs/cloud-agent](https://cursor.com/docs/cloud-agent)

### CI Autofix
Ewolucja harness: wcześniej hardcoded pobieranie logów CI → teraz agent dostaje `gh` CLI + duże outputy jako pliki do przeszukania; agent sam diagnozuje i naprawia.

### Multi-repo
Jeden agent może pracować na wielu repo (FE/BE/infra); otwiera PR w zmienionych repo. Long-running jeszcze nie dla multi-repo (stan docs).

## Human gates
| Gate | Opis |
|------|------|
| SCM connect (admin) | Wymagane przed startem |
| Spend limit | Przy pierwszym użyciu |
| PR merge | Człowiek (lub istniejące reguły repo) |
| Remote desktop | Opcjonalny takeover VM do ręcznego testu |
| Team follow-ups | Admin musi włączyć, by inni pisali do cudzego agenta |
| Hooks | `preToolUse`, `beforeShellExecution`, policy — Enterprise team/enterprise hooks |

## Eval / CI
- Agent buduje i testuje **w swojej VM** (nie tylko static diff).
- Artifacts: screenshots, videos, logs jako proof-of-correctness.
- Hooks uruchamiają formattery/audit przy tool use.
- CI Autofix zamyka pętlę z GitHub Checks.

## Multi-agent vs single
- Single cloud agent + **async subagents** (mogą przeżyć parent / inne pody).
- Dedicated **computer-use subagent** (osobny model routing, screen recording, VNC/Chrome w shared env).
- Równoległe niezależne cloud agents (N równolegle bez laptopa).

## Failure / retry
- Temporal: retries przy inference blip / pod replace / EC2 failure.
- Conversation layer: rewind stream po retry częściowego outputu.
- Self-healing direction: agent raportuje brak secrets / blocked network; „autoinstall” research path.
- Harness skew: cloud prompts bardziej autonomiczne (koszt idle block > lokalnie).

## Czego NIE automatyzuje
- Merge bez review (domyślnie handoff = PR)
- Magiczne env bez setupu (to główny failure mode jakości)
- User-level hooks z `~/.cursor/hooks.json` (niedostępne na cloud VM)
- Long-running multi-repo (ograniczenie docs)

## Open-source vs closed
**Closed** produkt. Publiczne docs + engineering blogs. Temporal = OSS dependency w stacku, nie sam agent.

## Kluczowe URL-e
- https://cursor.com/docs/cloud-agent
- https://cursor.com/blog/cloud-agent-lessons
- https://www.zenml.io/llmops-database/building-and-operating-agentic-ai-coding-products-at-scale-with-temporal
