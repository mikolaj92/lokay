# Dark factory — baza wiedzy

Zbiór notatek o tym, jak inni budują **dark AI software factory**:
issue / sygnał → kod → test → PR → (auto)merge.

**Uwaga nazewnicza:** to jest pętla **klepacza** (ticket-to-PR), nie Shapiro-L5 „cały produkt z spec”. Patrz [KLEPACZ.md](./KLEPACZ.md).

Metafora z produkcji: [lights-out manufacturing](https://en.wikipedia.org/wiki/Lights_out_%28manufacturing%29) —
fabryka działa bez ciągłej obecności operatora. W softwarze: człowiek pisze
spec/harness/politykę; maszyna dowozi PR-y.

## Co to NIE jest

- **Assisted IDE** (Cursor chat, Windsurf Cascade, Copilot chat) — człowiek w pętli na każdym kroku.
- **App generator** (Bolt, v0, Lovable) — greenfield UI z promptu, nie mill po istniejącym katalogu issue.
- **Benchmark harness** (SWE-bench runner) — ewaluacja, nie produkcyjna fabryka.

## Mapa folderu

| Ścieżka | Treść |
|---------|--------|
| [PATTERNS.md](./PATTERNS.md) | Wzorce kanoniczne |
| [ANTI_PATTERNS.md](./ANTI_PATTERNS.md) | Antywzorce (limbo, stuck, sklejone kroki) |
| [COMPARE.md](./COMPARE.md) | Macierz porównawcza |
| [LOKAY_LENS.md](./LOKAY_LENS.md) | Obserwacje względem Lokaya (bez recepty przepisania) |
| [SOURCES.md](./SOURCES.md) | Bibliografia URL |
| [CURSOR_SELF_DRIVING.md](./CURSOR_SELF_DRIVING.md) | Cursor: recursive planners (self-driving) |
| [MAZUR_AUTONOM.md](./MAZUR_AUTONOM.md) | Mazur autonom ↔ harness |
| [STRATEGY_AGENT_FIRST.md](./STRATEGY_AGENT_FIRST.md) | Teza: najpierw działający mill agentowy |
| [KLEPACZ.md](./KLEPACZ.md) | **Kanon:** ticket-to-PR / klepacz, nie L5 |
| [commercial/](./commercial/) | Produkty zamknięte / SaaS |
| [oss/](./oss/) | Open source i projekty „dosłownie dark factory” |
| [emerging/](./emerging/) | Sąsiednie / emerging |
| [github-shake/](./github-shake/) | Fale GitHub search (WAVE1 mills = 28 repos) |

## Najbliżej prawdziwej dark factory (skrót)

1. **peter-stratton/dark-factory (`godark`)** — CLI + Claude Code; implementer + 2 reviewerów; auto squash-merge albo `needs-human-review`.
2. **thegpvc/gp-foundry** — graf DOT → GitHub Actions; scout→builder→reviewer→fixer→merge_gate; self-heal cron.
3. **0-sayed/dark-factory** — Codex + Archon + Agent Orchestrator; bootstrap ręczny, potem autonomia.
4. **Factory.ai Missions** — multi-droid orchestration; headless `droid exec --mission`.
5. **Devin** — PR jako interfejs; auto-fix CI/review; merge zwykle ludzki (governance).

Reszta = mocne agenty SWE albo assisted coding — wartościowe mechanizmy, słabszy „mill”.
