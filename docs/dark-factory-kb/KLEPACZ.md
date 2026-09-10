# Klepacz = ticket-to-PR (nie L5 dark factory)

Status: **kanon CEO 2026-09-10**. Precyzuje, *co* budujemy, gdy rynek mówi „dark factory”.

## Nieporozumienie rynku

„Dark factory” w sensie Shapiro (spec → cały produkt poprawny, lights-out bank) to **marketingowy sufit L5**.

To, czego szukamy, to **Level 3–4 na jednej roli**: zastąpić *klepacza* + babysitting kolejki, nie inżyniera, BA, UX, QA-strategię ani DevOps.

## Łańcuch ról (zostaje)

| Rola | Zostaje? | Uwaga |
|------|----------|--------|
| Analityk / PO | tak | rozbija potrzebę |
| UX/UI | tak | input, nie wykonawca w pętli klepacza |
| Inżynier | **tak** | rozwiązanie, scope, add/remove, decyzja |
| **Klepacz** | **automat** | issue → diff → PR |
| QA (strategia) | tak | holdouty ludzkie; agent odpala testy z ticketu |
| DevOps | tak | CI, tokeny, branch protection; agent nie osłabia CI |

## Co zdejmujemy

1. Ręczne „weź ten issue”
2. Ręczne „zmerguj tę PR-kę” (opcjonalnie, polityką)

## Uczciwe nazwy

- ticket-to-PR worker / junior implementer agent
- background coding agent
- label-triggered implementer
- praktyka 2026: etykieta `ready-for-agent` / `auto-fix` / `guild-auto`

Cytat ramowy ([berenddeboer/ready-for-agent](https://github.com/berenddeboer/ready-for-agent)):

> You design, you architect, you verify where needed — the harness removes the babysitting between issue and merged PR.

## Pętla (wąska)

```text
inżynier pisze issue (= spec)
    → etykieta ready-for-agent
    → harness (daemon / Action / lokalny)
         worktree · agent czyta TYLKO issue + dozwolone pliki
         minimalny diff · testy z issue · draft PR (Closes #N)
    → CI + opcjonalnie agent-review
    → Merge Policy: Off | Classify | Always
```

Agent **nie wybiera** pracy. Etykieta = „weź”, bez czatu.

## Realizacje tej mrówki (nie L5)

| System | Mechanizm |
|--------|-----------|
| [ready-for-agent](https://github.com/berenddeboer/ready-for-agent) | Label → worktree → agent → PR → Off/Classify/Always |
| Claude Code Action | label / automation prompt → `claude/issue-N` → PR |
| Codex `codex-auto` | label → CLI w Actions → PR |
| Guild `guild-auto` | Planner/Implementer/Reviewer → draft PR; ludzie właściciele wyniku |
| Copilot cloud / background | issue → draft PR (małe, jasne, z komendą weryfikacji) |
| Ralph Loop / VPS skrypt | ready-for-agent → worktree → test → drugi model review → draft |

## Granica klepacz / inżynier

| Klepacz (automatyzuj) | Inżynier (zostaje) |
|-----------------------|---------------------|
| Issue mówi CO i JAK sprawdzić | Issue nie istnieje albo jest złe |
| Zmiana w istniejącym wzorcu | Trzeba wymyślić wzorzec |
| Acceptance w teście | Acceptance polityczne/produktowe |
| Mały blast radius | Auth, billing, schema, UX flow |
| „Zrób X w A/B, nie ruszaj C” | „Czy X w ogóle powinno powstać?” |

Lekcja (DEV 2026-09-07): 23 PR / 14 merge / 3 revert / near-miss drop tabeli — linie OK, **decyzja** zła. Auto-merge = polityka, nie religia.

## Merge Policy (gałka)

- **Off** — start: klepacz pisze PR, człowiek merguje
- **Classify** — auto tylko niskie ryzyko
- **Always** — tylko gdy CI jest wyrocznią (docs, lockfile, wąski bugfix z testem)

## Interfejs = issue, nie prompt

Szablon agent-ready:

- Outcome
- In scope / Out of scope
- Context (pliki, decyzja, incydent)
- Acceptance (Given/When/Then)
- Allowed actions (ścieżki, komendy)
- Ask or stop before (auth, billing, migracje, deps)
- Verification (testy / log / screenshot)

Twardo: blokuj etykietę `ready-for-agent`, dopóki brakuje sekcji — taniej niż „lepszy model”.

## Inteligentny klepacz jest gorszy

Im większa org, tym ważniejsze: mrówka **głupia i posłuszna**. Agent „ulepszający po drodze” = ryzyko.

## Relacja do Lokaya

- `DARK_FACTORY_ARCHETYPE.md` = dojrzały *graf* (proces) — OK jako cel długi.
- `STRATEGY_AGENT_FIRST.md` = kolejność budowy.
- **Ten dokument** = produktowa definicja skutku: kolejka klepacza, nie bank-od-A-do-Z.

Lokay, który nie dowozi issue→PR, nie jest „prawie L5” — jest zepsutą mrówką. Najpierw wąska pętla musi działać.
