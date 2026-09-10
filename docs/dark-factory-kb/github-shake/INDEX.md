# github-shake — INDEX

Głęboki przegląd publicznych repozytoriów / wzorców pod kątem **dark AI software factory / autonomous coding mill**.

Język: PL summaries, EN nazwy/URL. Stan: **2026-09-10** (Europe/Warsaw).

| Wave | Plik | Zakres | Wynik |
|------|------|--------|-------|
| WAVE1 | [WAVE1_MILLS.md](./WAVE1_MILLS.md) | Keyword deep search: dark-factory, godark, ouroboros, genesis, remote-factory, evo, miniforge, robotsix-mill, OpenFactory, DAGent, lights-out, coding mill, issue→PR | **28** real mill repos |
| WAVE2 | [WAVE2_RECURSIVE.md](./WAVE2_RECURSIVE.md) | Recursive planner–worker, RAH/RLM, ouroboros/ACE, antykruche fleety | Archetypy A–H + checklist |
| WAVE3 | [WAVE3_DETERMINISTIC.md](./WAVE3_DETERMINISTIC.md) | Deterministic spines: Agentless, DOT/GHA, Temporal, sealed tests, policy gates | Macierz agent-free vs LLM-forced |
| WAVE4 | [WAVE4_KEYWORDS.md](./WAVE4_KEYWORDS.md) | Marketing keyword sweep (`software factory`, `lights out`, `autonomous PR`, …) | Honesty scale: real mill / assisted / vapor |

## WAVE1 — metoda

- `WebSearch` + `gh search repos` / `gh api repos/...`
- Kryterium „real”: czytelny README, mechanizm issue/spec → code → test/review → PR/merge (lub closed evolution loop)
- Wykluczone: assisted IDE, manufacturing OpenFactory, DAG-lib „DAGent” bez mill, `remote_factory_girl`

## Archetype tags (WAVE1)

| Tag | Znaczenie |
|-----|-----------|
| `issue-to-pr` | Ticket/issue → implement → PR |
| `harness-cli` | CLI wokół Claude Code / Codex / Copilot |
| `dot-graph` | Orkiestracja jako Graphviz DOT / workflow-as-code |
| `holdout-judge` | Scenariusze holdout + LLM judge / sealed envelope |
| `fleet` | Flota ról (PM/arch/coder/QA) + replanning |
| `self-improve` | Meta-loop: fabryka poprawia siebie / agentów |
| `control-plane` | Provisioning sandboksów + credentials + lifecycle |
| `protocol` | Skill/protocol (nie pełny runtime) |
| `sqlite-mill` | Lokalna kolejka SQLite, forge dopiero na deliver |
| `evolution` | Continuous improve / score-gated keep |
