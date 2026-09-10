<!-- spine: spine_deterministic -->
# Inngest — event-driven step functions jako spine

**spine:deterministic**  
**Confidence: 84** — durable steps (`step.run` / `step.waitForEvent`) = granice trwałości; popularny wybór TS/Python na event→agent→PR; routing i fan-out w kodzie funkcji, nie w LLM.

## Co to jest

**Inngest** modeluje klepacza jako **funkcję sterowaną eventem** (`github/issue.labeled`). Każdy `step.run("implement", …)` / `step.run("tests", …)` jest checkpointem: retry dotyczy tylko padniętego kroku; `step.waitForEvent` = HITL (np. `pr/approved`). Orkiestracja to zwykły TypeScript/Python z jawnymi krokami — LLM siedzi *wewnątrz* wybranego stepu, nie decyduje o grafie.

## Graf

```mermaid
flowchart TD
  ev[CODE: event github/issue.labeled ready-for-agent] --> fn[CODE: Inngest function]
  fn --> s1[CODE step.run: hydrate issue + branch]
  s1 --> s2[LLM step.run: coding agent]
  s2 --> s3[CODE step.run: tests]
  s3 -->|fail & n less max| s2
  s3 -->|ok| s4[CODE step.run: open PR]
  s4 --> wait[CODE step.waitForEvent: human/ci.approved]
  wait --> s5[CODE step.run: merge or comment]
```

## LLM vs code (węzły)

| Węzeł | Typ | Uwaga |
|-------|-----|--------|
| Function control flow, fan-out, sleeps, waitForEvent | **CODE** | Event history / step memoization |
| hydrate, tests, `gh`, merge | **CODE** `step.run` | Idempotent keys |
| coding agent / summary comment | **LLM** `step.run` | Jedyny płatny slot |
| „czy mergować?” | **CODE** + event | Nie LLM judge jako jedyna bramka |

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | Inngest event (GitHub webhook relay, cron, custom) |
| Spine | Inngest Cloud lub self-host dev server |
| Agent leaf | Claude/Codex SDK w jednym stepie z timeoutem |
| HITL | `step.waitForEvent` / invoke another function |
| Fit | Event-reactive pipelines; mniej naturalne na 2h linear agent loop → rozważ Trigger.dev |

## Linki

- https://www.inngest.com/docs/agents
- https://www.inngest.com/docs/features/inngest-functions/steps-workflows
- Porównanie 2026: https://tanayshah.dev/blog/trigger-vs-inngest-vs-temporal-agents/
