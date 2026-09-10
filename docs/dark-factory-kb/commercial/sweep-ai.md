# Sweep AI

**Typ:** open-source (self-hostable) + historycznie GitHub App SaaS  
**Producent:** Sweep AI (sweepai/sweep)  
**Rola:** GitHub Issue → plan plików → sandbox validate → PR; async CI fix loop

## Architektura

```
GitHub webhook (Issue created / "Sweep" label / "Sweep: …" title)
    → on_ticket
    → hybrid search (lexical + vector) + Python AST dependency graph
    → get_files_to_change (NL per-file instructions)
    → create_branch + multi-file edits (programmatic refactors / Rope DSL)
    → sandbox: unit tests + formatters
    → open Pull Request
    → watch CI → iterate until green (lub człowiek przejmuje)
    → opcjonalnie: resolve merge conflicts via follow-up PR
```

Źródła: [sweepai/sweep docs index](https://github.com/sweepai/sweep/blob/main/docs/pages/index.mdx), [AI code planning blog](https://github.com/sweepai/sweep/blob/main/docs/pages/blogs/ai-code-planning.mdx), [api.py](https://github.com/sweepai/sweep/blob/main/sweepai/api.py)

### Mechanizmy warte skopiowania do fabryki
- **Topological edit order** z import graph (uniknięcie połówek API change).
- **Context pruning** + AST search (recall/precision).
- **Sandbox validation przed PR** (nie „diff-only”).
- **CI feedback loop** po otwarciu PR.
- **sweep.yaml** config (branch TTL, gha_enabled, rules).

## Human gates
| Gate | Opis |
|------|------|
| Issue quality | Opis jak dla juniora — krytyczny |
| Label / prefix | Explicit assign do Sweep |
| PR review + merge | Człowiek |
| Comment replies | Sweep adresuje komentarze na PR |

## Eval / CI
- Lokalny sandbox test/format przed PR.
- Po PR: definiuje/uruchamia GitHub Actions; async aż CI pass.
- Rules PRs (`[Sweep Rules]`) auto-close gdy stale unclean.

## Multi-agent vs single
**Single-pipeline agent** (plan→edit→validate). Równoległość = wiele ticketów naraz, nie wewnętrzny swarm.

## Failure / retry
- Iteracja na compiler/test errors w sandboxie.
- CI fail → kolejna runda patchy.
- Merge conflict resolver PR.
- Periodic merge main→sweep branches (api maintenance loop).

## Czego NIE automatyzuje
- Duże niejasne features (pozycjonowanie: small bugs/refactors/unit tests)
- Merge bez review
- Non-GitHub native (rdzeń = GitHub webhooks)

## Open-source vs closed
**Open-source** (repo sweepai/sweep; self-host). GitHub App był hosted path. Stan aktywności produktu bywa zmienny — weryfikować repo przed adopcją.

## Kluczowe URL-e
- https://github.com/sweepai/sweep
- https://github.com/sweepai/sweep/blob/main/docs/pages/index.mdx
- https://github.com/sweepai/sweep/blob/main/docs/pages/blogs/ai-code-planning.mdx
