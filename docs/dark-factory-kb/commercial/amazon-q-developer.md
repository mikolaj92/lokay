# Amazon Q Developer agent (GitHub / GitLab Duo)

**Typ:** zamknięty (AWS)  
**Producent:** Amazon Web Services  
**Rola:** issue→PR development agent + automated PR code review agent w GitHub/GitLab

## Architektura

```
GitHub Issue + label "Amazon Q development agent" LUB komentarz `/q dev`
    → Q development agent (kontekst: issue title/body + repo)
    → generuje zmiany → otwiera Pull Request + summary
    → feedback `/q …` na PR → iterate + nowe commity

Osobno:
New/reopened PR → Q code review agent (auto)
    → summary + threaded findings + suggested fixes (commit optional)
    → `/q review` dla kolejnych przeglądów (auto NIE na każdym kolejnym commit)
```

Źródła: [Amazon Q for GitHub](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/amazon-q-for-github.html), [Feature development](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-feature-development.html), [Code reviews](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-code-reviews.html)

### Project rules
Markdown w `.amazonq/rules/` — kontekst dla generate + review (shift-left standards).

### Inne powierzchnie
- IDE Amazon Q / agents (transform, feature dev lokalnie) — poza scope GitHub factory, ale ten sam brand.
- GitLab Duo with Amazon Q — parallel integration path.

## Human gates
| Gate | Opis |
|------|------|
| Label / `/q dev` | Explicit kickoff |
| Commit suggested fixes | Człowiek akceptuje fix z review |
| Merge | Człowiek (+ zalecane: require conversation resolution) |
| Permissions | App install / feature flags |

## Eval / CI
- Review agent = static/security/quality pass na diff (nie pełny test runner w docs GitHub flow).
- Development agent: docs nie gwarantują pełnego lokalnego test harness jak Cursor VM — zależne od tego, co agent wykona w swoim backendzie.
- Reguły repo + wymaganie resolved conversations = enforcement.

## Multi-agent vs single
**Dwa wyspecjalizowane agenty produktowe** (dev + review), nie orchestrator Missions. Iteracja = ten sam agent na feedback.

## Failure / retry
- Komentarz `/q` z instrukcją → kolejna implementacja.
- Brak auto-re-review na każdym push — świadomie `/q review`.
- Preview status historycznie — sprawdzać aktualny GA w docs AWS.

## Czego NIE automatyzuje
- Merge
- Pełny durable multi-day workflow orchestration
- Auto review na każdym subsequent commit (domyślnie)
- Cross-platform poza wspieranymi integracjami

## Open-source vs closed
**Closed.** AWS docs publiczne; rules format = plain Markdown w repo.

## Kluczowe URL-e
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/amazon-q-for-github.html
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-feature-development.html
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-code-reviews.html
- https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/third-party-integration.html
