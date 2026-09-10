# Strategia: najpierw działający mill agentowy, potem deterministyka

Status: **teza CEO (2026-09-10)** — zapis idei, nie commit do zmiany runtime Lokaya w tym PR.

## Kontekst

Dotychczasowa linia Lokaya (patrz `docs/DARK_FACTORY_ARCHETYPE.md`):

> Graf jest wartością, ponieważ graf jest procesem. Węzły są wymiennymi wykonawcami.

To zostaje prawdziwe jako **cel dojrzały**. Ale empirically: gruby deterministyczny graf + LaunchAgent + stuck/ready/leftover **nie dowozi** dziś stabilnego issue→PR→merge.

## Nowa kolejność budowy

```text
1) Cokolwiek działającego end-to-end (nawet ~100% agentów)
   → jeden ticket → sandbox → PR → (gate) → merge
2) Obserwuj gdzie agent jest zbędny / szkodliwy / drogi
3) Wycinaj te miejsca w małe deterministyczne programy (kontrakt I/O)
4) Zostaw LLM tylko przy wysokiej entropii
```

To jest **odwrócenie kolejności implementacji**, nie odrzucenie prawa grafu.
Graf zostaje mapą; najpierw mapa może być prawie cała „agent w slocie”, potem sloty twardnieją.

## Co działa u innych (skrót)

| System | Start | Deterministyka |
|--------|-------|----------------|
| Copilot / Jules / Codex cloud | Agent session → PR | Merge + branch protection ludzkie/CI |
| Cursor self-driving | Rekurencyjni plannerzy + workerzy (same agenty) | Izolacja kopii repo, handoff, anti-fragile |
| godark | Agenty Claude Code | Guard rails, protected files, merge/escalate |
| gp-foundry | Agenty w Actions | **Skompilowany** graf DOT + merge_gate policy |
| Ouroboros / remote-factory | Agent-first SM | Typed contracts, eval gates, meta-improve |
| evo | Closed-loop evolve | Benchmark gate zanim merge |

Żaden poważny mill nie zaczyna od idealnego Unixowego grafu bez dowozu.
Zaczynają od **pętli która produkuje PR**, potem dokręcają harness.

## Mapowanie na działy Lokaya (hipoteza ścieżki)

| Teraz (ciężki graf) | Agent-first MVP | Późniejsza wycinka |
|---------------------|-----------------|--------------------|
| `issue_triage` Fala | Agent: „weź 1 OPEN issue” albo assign | Deterministyczny list+filtry |
| `executor` | Jeden coding agent → PR | Worktree/lease/test command jako skrypty |
| `pr_triage` | Agent review **lub** sam CI+auto-merge policy | Merge policy bez LLM |
| `pr_repair` | `@agent` na czerwonym PR | Ten sam branch + lokalny test gate |
| `self_repair` | Watchdog „czy był merge?” | Fingerprint stall dopiero gdy mill żyje |

## Kryterium sukcesu MVP

Nie: „ładny graf w Fali”.
Tak: **N zmergowanych `ai/fix` w oknie 1h/8h/24h** na tipie hosta — jak prawo pomiaru CEO.

## Ryzyka

- Zostanie przy 100% agentach na zawsze (koszt, nondeterminism) — mitigacja: lista „kandydatów do wycinki” po każdym tygodniu.
- Wrócenie limbo (`needs-human`) zamiast retry/split — zakaz trwałego parkowania.
- Continuous-executor pathologie (Cursor) — nie składać plan+spawn+review+merge w jednego agenta.

## Powiązane

- [CURSOR_SELF_DRIVING.md](./CURSOR_SELF_DRIVING.md)
- [MAZUR_AUTONOM.md](./MAZUR_AUTONOM.md)
- [LOKAY_LENS.md](./LOKAY_LENS.md)
- `docs/DARK_FACTORY_ARCHETYPE.md` (dojrzały cel: graf)
