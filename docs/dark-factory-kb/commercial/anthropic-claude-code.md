# Anthropic Claude Code — autonomous loops

**Typ:** closed model + agent product; CLI/Desktop/VS Code extension (paid plans)  
**Producent:** Anthropic  
**Rola:** lokalne/cloud routines + „loop engineering” + dynamic workflows (setki subagentów) — bliżej **fabryki na laptopie/CI** niż czystego SaaS issue→PR (choć GitHub Code Review istnieje)

## Architektura pętli (oficjalna taksonomia Anthropic)

| Loop | Trigger | Stop | Primitives |
|------|---------|------|------------|
| Turn-based | User prompt | Model „done” lub brak kontekstu | agentic loop + verification skills |
| Goal-based | Prompt + `/goal` | Warunek spełniony LUB max turns | osobny **evaluator model** sprawdza goal |
| Time-based | `/loop` interval | Cancel / PR merge / queue empty | `/loop` lokalnie; `/schedule` → cloud routine |
| Proactive | Event/schedule, bez człowieka w real-time | Per-task goal; routine aż wyłączysz | compose + auto mode + dynamic workflows |

Źródło: [claude.com/blog/getting-started-with-loops](https://claude.com/blog/getting-started-with-loops) (30 Jun 2026)

### Dynamic workflows
- Claude **pisze skrypt JS** orkiestracji; runtime wykonuje w tle (poza conversation context).
- Cap: ~**16 concurrent**, do ~**1000 total** agents per run (third-party docs aligned z research preview).
- Resume/checkpoint w `/workflows`; intermediate results w zmiennych skryptu.
- **ultracode** (`xhigh` + auto workflow orchestration): Claude sam decyduje kiedy spawnować workflow.
- Git handoff / worktrees: parallel solutions + adversarial judge w przykładach proactive.

Źródła: [code.claude.com/docs/en/workflows](https://code.claude.com/docs/en/workflows), [Introducing dynamic workflows](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code)

### Typowy factory shape
```
/schedule | event
  → /goal (done = tests green + lint)
  → workflow: explore N solutions || implement || adversarial review
  → /code-review lub GitHub Code Review
  → człowiek merge
```

## Human gates
| Gate | Opis |
|------|------|
| Auto mode vs permissions | Bez auto mode — pytania o tool permission |
| Plan/workflow approve | Zależnie od settings; ultracode agresywniejszy |
| `/goal` turn caps | Twarde ograniczenie kosztu/iteracji |
| PR merge | Poza Claude Code — człowiek / branch protection |
| Admin controls | Enterprise/Team: dostępność workflows |

## Eval / CI
- **Verification skills** (`SKILL.md`) — deterministyczne checki (Lighthouse, browser MCP, test suites).
- Goal evaluator ≠ coding model (świeższy, szybszy model).
- Drugi agent do `/code-review` — uniknięcie bias autora.
- External CI: agent może `/loop` na PR i fixować failing checks.

## Multi-agent vs single
- Single agentic loop = default.
- Subagents / agent teams = turn-by-turn orchestration w kontekście Claude.
- Dynamic workflows = **code-orchestrated multi-agent** (skala fabryki).

## Failure / retry
- Goal-based: evaluator odsyła do pracy aż goal lub max turns.
- Workflow resume: completed agents cached; reszta fresh.
- Token discipline: pilot na slice repo; tańsze modele na routine; skrypty zamiast reasoning na deterministic steps.

## Czego NIE automatyzuje
- Domyślny lights-out merge do produkcji
- Pełny managed multi-tenant Devbox SaaS jak Devin (Claude Code = primarily developer machine + scheduled cloud routines)
- „Nieskończona” pętla bez goal/caps (koszty eksplodują — oficjalne ostrzeżenie)

## Open-source vs closed
**Closed** product + models. Docs/blog publiczne. Skills format społecznościowy / kopiowalny.

## Kluczowe URL-e
- https://claude.com/blog/getting-started-with-loops
- https://claude.com/blog/introducing-dynamic-workflows-in-claude-code
- https://code.claude.com/docs/en/workflows
