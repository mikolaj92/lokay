# OpenAI Codex (Cloud + CLI + IDE)

**Typ:** zamknięty (OpenAI) — CLI częściowo OSS w ekosystemie; cloud closed  
**Producent:** OpenAI  
**Rola:** cloud sandbox task → diff/PR; lokalny CLI loop; GitHub `@codex` review/fix; skills + AGENTS.md

## Architektura

```
Trigger (chatgpt.com/codex / IDE / CLI `codex cloud` /
         GitHub @codex / Linear / automations)
    → Cloud environment (izolowany kontener, ephemeral)
    → clone repo + AGENTS.md / skills / MCP / subagents
    → implement → run tests (wg guidance)
    → diff + opcjonalny PR
    → człowiek: review / iterate / merge
```

### Warstwy customizacji (oficjalne)
1. **AGENTS.md** — trwałe reguły repo (build/test, conventions); feedback loop: popraw → zapisz do AGENTS.md
2. **Memories** — kontekst z prior work
3. **Skills** (`SKILL.md` + scripts) — powtarzalne workflow; progressive disclosure metadata→body
4. **MCP** — Linear/GitHub/Figma/docs
5. **Subagents** — specjalizacja narzędzi/ról

Źródło: [developers.openai.com/codex/concepts/customization](https://developers.openai.com/codex/concepts/customization)

### Cloud vs always-on
- Cloud: disposable container; parallel tasks; shared usage window z lokalnym Codex.
- CLI local: sandbox policies (`read-only` | `workspace-write` | `danger-full-access`).
- `codex cloud exec --env … --attempts` (best-of-N, experimental).

### GitHub surface
- `@codex review` → code review (P0/P1 focus); Automatic reviews w settings
- Inne `@codex …` → cloud chat z kontekstem PR; może pushować fix na branch
- Skill **babysit-pr** (openai/codex): poll CI/reviews/mergeability; retry flaky ≤3; auto-fix branch issues

Źródła: [Codex GitHub](https://developers.openai.com/codex/third-party/github), [babysit-pr SKILL](https://github.com/openai/codex/blob/main/.codex/skills/babysit-pr/SKILL.md), [workflows](https://developers.openai.com/codex/workflows)

## Human gates
| Gate | Opis |
|------|------|
| PR create/merge | Cloud oddaje diff/PR; merge u człowieka |
| Approvals (local) | Sandbox + ask-for-approval modes |
| Code review settings | Admin włącza review / automatic reviews |
| Security findings → PR | Człowiek tworzy remediation PR z Findings UI |

## Eval / CI
- Testy w sandboxie jeśli env/AGENTS.md je definiuje.
- `openai/codex-action` — agent w GitHub Actions jako quality gate.
- babysit-pr / watch CI: klasyfikacja flaky vs branch-related.
- `/review` lokalnie przed pushem.

## Multi-agent vs single
- Domyślnie **single agent** per cloud task.
- **Subagents** do specjalizacji.
- Best-of-N (`--attempts`) = równoległe próby, nie full factory orchestrator jak Devin/Factory Missions.

## Failure / retry
- Cloud task fail → nowy task / follow-up w tym samym wątku.
- babysit-pr: retry flaky CI do 3×; patch tylko gdy failure branch-related.
- Local sandbox: polityki ograniczają blast radius.

## Czego NIE automatyzuje
- Domyślny auto-merge produkcji
- Persistent always-on maszyna (wymaga własnego hosta)
- Gwarantowany dostęp do zewnętrznych DB/secrets poza skonfigurowanym env/MCP
- Pełny multi-day orchestrator z checkpointami jak Devin Dynamic Workflows / Claude ultracode

## Open-source vs closed
- **Cloud + modele:** closed
- **CLI / skills examples / actions:** częściowo publiczne w github.com/openai/codex

## Kluczowe URL-e
- https://developers.openai.com/codex/concepts/customization
- https://developers.openai.com/codex/workflows
- https://developers.openai.com/codex/third-party/github
- https://developers.openai.com/codex/security/setup
- https://github.com/openai/codex/blob/main/.codex/skills/babysit-pr/SKILL.md
