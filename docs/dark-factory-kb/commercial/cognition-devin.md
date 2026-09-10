# Cognition Devin

**Typ:** zamknięty (closed) SaaS / enterprise cloud agent  
**Producent:** Cognition  
**Rola w „fabryce”:** autonomiczny SWE agent → plan → kod → testy → PR (często stacked) → review człowieka

## Architektura (queue → code → test → PR → merge?)

```
Trigger (Slack / Web / Jira / API)
    → Brain (stateless reasoning w chmurze Cognition)
    → Devbox (izolowana VM: shell, editor, browser, git)
    → pętla: edit → run → read logs → self-fix
    → git branch + Pull Request (opcjonalnie stacked PRs)
    → człowiek: review / merge
    → [opcjonalnie] Dynamic Workflow: Python orchestrator spawnuje wiele sesji
```

### Brain vs Devbox
- **Brain:** bezstanowy koordynator rozumowania w chmurze Cognition (analogia do architektury Copilota — model poza workspace).
- **Devbox:** bezpieczne środowisko wykonawcze (kontener/VM) z narzędziami deweloperskimi; Brain wysyła polecenia (shell, edycje plików), Devbox zwraca stdout/drzewa katalogów.
- **Enterprise:** Enterprise Cloud (multi-tenant) lub Customer Dedicated Deployment (single-tenant VPC + Private Link / IPSec).

Źródła: [docs.devin.ai enterprise overview](https://docs.devin.ai/enterprise/deployment/overview), [Fastio architecture writeup](https://fast.io/resources/cognition-devin-ai-architecture/).

### Dynamic Workflows (multi-agent factory)
Deterministyczny skrypt Python napisany przez Devina orkiestruje zespół agentów:
- `register_workflow` → `agent(prompt, schema=...)` → `pipeline` / `parallel`
- Domyślnie każde `agent()` = **osobna sesja Devin na własnej VM**
- Handoff kodu przez **git branche** (structured output: nazwa brancha), nie współdzielony FS
- Resume: skrypt odtwarzany od góry; ukończone wywołania replay z hash(prompt+schema); budżet runu do **7 dni**
- Human gate: approve skryptu workflow (chyba że auto-approve w settings)

Źródło: [docs.devin.ai Dynamic Workflows](https://docs.devin.ai/work-with-devin/dynamic-workflows)

### Stacked PRs
Duże zadania → stos mniejszych PR-ów (GitHub native stacked PRs). Devin rebasuje downstream po komentarzach / merge dolnej warstwy; monitoruje CI + mergeability całego stosu. Planowanie stacku wspiera DeepWiki (mapa architektury repo).

Źródło: [devin.ai/blog/introducing-pr-stacks](https://devin.ai/blog/introducing-pr-stacks)

## Human gates
| Gate | Opis |
|------|------|
| Task intake | Człowiek (lub ticket) definiuje zadanie |
| Workflow script approve | Domyślnie wymagane przed Dynamic Workflow |
| PR review + merge | **Merge nie jest lights-out** — standardowy review |
| PR comments | Devin może odpowiadać i pushować fixy w aktywnej sesji |
| Enterprise feature flags | Dynamic Workflows off by default w Enterprise |

## Eval / CI
- Agent sam uruchamia testy w Devboxie; czyta traceback i iteruje.
- Po PR: natywne CI repo (GitHub Actions itd.) jest sygnałem; stacked PRs śledzą CI per warstwa.
- Brak publicznego „auto-merge bez review” jako domyślnego produktu.

## Multi-agent vs single
- **Single session:** klasyczny Devin na jednej Devbox.
- **Child agents:** parent spawnuje równoległe child sessions na subtaski.
- **Dynamic Workflows:** skrypt = orchestrator; multi-agent z deterministycznym control flow + structured I/O.

## Failure / retry
- Non-zero exit / failing tests → self-correction loop (czytaj log → edytuj → rerun).
- Workflow: failed agent — skrypt decyduje (skip / default / retry / fail run); resume retryuje failed agents nowymi sesjami.
- Interrupted workflow: resume z run ID.

## Czego NIE automatyzuje (typowo)
- Merge do main / produkcja bez ludzkiego approve
- Własne decyzje produktowe / scope ambiguous
- Dostęp do prywatnych sieci bez Enterprise connectivity
- Tworzenie nowych repozytoriów (wg przewodników integracyjnych)

## Open-source vs closed
**Closed.** Dokumentacja publiczna + blogi; runtime i model Cognition nie są open-source.

## Kluczowe URL-e
- https://docs.devin.ai/enterprise/deployment/overview
- https://docs.devin.ai/work-with-devin/dynamic-workflows
- https://devin.ai/blog/introducing-pr-stacks
- https://fast.io/resources/cognition-devin-ai-architecture/
