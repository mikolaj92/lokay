# peter-stratton/dark-factory (`godark`)

- Repo: https://github.com/peter-stratton/dark-factory
- Docs: https://godarkfactory.com
- Stack: Go CLI + Claude Code + GitHub + Docker sandbox

## Teza

Ludzie decydują *co* i *jak pasuje* (roadmap, warstwy architektury, konwencje, issue specs).
Agenty piszą kod w harnessie. Sam projekt jest budowany przez własny pipeline (`godark run`).

## Pipeline (10 kroków)

1. Fetch issue z milestone (priorytet p1→p3)
2. Resolve dependencies (`Blocked by` / `Depends on`)
3. **Implementer** — Claude Code: kod + unit testy + PR
4. **Guard rails** — PR istnieje, `Closes #N`, protected files nietknięte
5. **Quality reviewer** — osobna instancja; security/perf/quality; nie edytuje plików
6. **Functional reviewer** — scenario specs → ephemeral integration tests
7. Retry loop (max N na gate)
8. **Merge or escalate** — squash-merge albo label `needs-human-review`
9. Punchlist — 3–5 konkretnych manual acceptance checkboxów
10. Następne odblokowane issue

## Mechanizmy warte skopiowania myślowo

- Trzy agenty z izolacją uprawnień (reviewer nie pisze plików)
- Architecture-as-code (`godark vet`)
- Dialog na PR jako audyt
- Pełny sandbox Docker domyślnie
- Single binary, bez floty MCP

## Limbo

Ma escape: `needs-human-review` po failu gate — świadoma eskalacja, nie nieskończone parkowanie intake.
