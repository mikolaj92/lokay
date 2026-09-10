# WAVE3 — Deterministic approaches to AI software factories

> **Cel fali:** znaleźć podejścia *bardziej deterministyczne* niż wolny ReAct/tool-loop — gdzie orkiestracja, bramki i weryfikacja są kodem/grafem, a LLM jest tylko w jawnych slotach.
>
> **Pytanie przewodnie:** *co może zostać agent-free, a gdzie LLM jest wymuszony?*

Powiązania w KB: `oss/agentless.md`, `oss/gp-foundry.md`, `PATTERNS.md` (P1.1–P1.3, P2.1, P4.1, P5.3).

---

## 1. Teza

„Deterministyczna fabryka” ≠ „zero LLM”. Oznacza:

1. **Topologia stała** — fazy / DAG / FSM zdefiniowane przed runem (nie odkrywane przez model).
2. **Routing bez tokenów** — warunki, pętle, escalate/merge to skrypt / Rego / Temporal / GHA, nie kolejny prompt.
3. **LLM w slotach** — lokalizacja, patch, czasem review/test-gen; nigdy „zarządzanie transakcją merge”.
4. **Oracle poza modelem** — testy, sealed suite, policy-as-code, CI — fail-closed.

Antyteza: agent z otwartym shellem i budżetem „aż się uda” (SWE-agent / OpenHands-class). To WAVE osobna; tu zbieramy **ściślejszy harness**.

---

## 2. Mapa podejść (GitHub + papers)

| Podejście | Rdzeń determinizmu | LLM gdzie? | Źródła |
|-----------|-------------------|------------|--------|
| **Agentless** (UIUC) | Stałe 3 fazy: localize → repair → validate | Każda faza (prompt), **bez** tool-loop / planowania | [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless), arXiv [2407.01489](https://arxiv.org/abs/2407.01489), FSE’25 |
| **gp-foundry DOT→GHA** | Kompilator `harness.dot` → workflows; model-check pętli; stan w labels/PR | Role (scout/builder/reviewer/…) w jobach; **merge_gate = policy YAML** | [thegpvc/gp-foundry](https://github.com/thegpvc/gp-foundry) |
| **Temporal workflows** | Replay-safe Workflow (deterministyczny) + Activities (I/O) | LLM/tool **tylko** w Activities; historia zdarzeń = źródło prawdy | [temporal.io AI ref](https://go.temporal.io/platform-hub/ai-engineering/ai-reference-architecture), [temporal-ai-agent](https://github.com/temporal-community/temporal-ai-agent), [temporal-agent-harness](https://github.com/temporal-community/temporal-agent-harness); Codex na Temporal (OpenAI) |
| **Pure script issue→PR** | Shell + `gh`/`jq` + cron GHA; board/labels = FSM | Jedna (lub kilka) sesji CLI modelu w slotach implement/fix | [a7t-ai/three-body-agent](https://github.com/a7t-ai/three-body-agent), [TheCraigHewitt/agent-pipeline](https://github.com/TheCraigHewitt/agent-pipeline) |
| **Fixed localize-repair-validate** | Tożsamo z Agentless; warianty: multi-sample + majority vote + AST canonicalize | Patch / loc / repro-test gen | Agentless + analiza [eulerfold](https://www.eulerfold.com/research-decoded/agentless-demystifying-software-engineering-agents) |
| **Policy-as-code merge gates** | OPA/Conftest/Rego, YAML size/path gates, required checks — exit code | *Opcjonalnie* LLM-review **przed** bramką; bramka bez LLM | Conftest CI, [OpenAgentSecurity](https://github.com/mateaix/openagentsecurity), gp-foundry `agents/policy/merge.yaml`, SLSA/SBOM gates |
| **Sealed / holdout tests** | Hash + vault; builder nigdy nie widzi suite; score z exit codes | Generacja sealed (osobny model/family); **grading = deterministyczny** | [shadow-score-spec](https://github.com/DUBSOpenHub/shadow-score-spec), [dark-factory](https://github.com/DUBSOpenHub/dark-factory), [holdout](https://github.com/brevity1swos/holdout), SaifCTL |
| **Conductor (MS)** | YAML workflow + Jinja routes; orchestration = 0 tokenów | Kroki `type: agent`; kroki `script` / `human_gate` bez LLM | [microsoft/conductor](https://github.com/microsoft/conductor) |
| **PlanCompiler** | Registry węzłów → walidacja 7 checków → kompilacja Pythona; **brak** LLM po planie | **Jedyny** call: wybór węzłów + parametry JSON | [prnvh/plancompiler](https://github.com/prnvh/plancompiler), arXiv [2604.13092](https://arxiv.org/abs/2604.13092) |

---

## 3. Agentless — kanon „fixed localize-repair-validate”

**Paper:** Xia et al., *Agentless: Demystifying LLM-based Software Engineering Agents* (arXiv 2407.01489; FSE 2025).

### Pipeline (sztywny)

1. **Localization (hierarchia):** struktura drzewa repo → LLM top-N plików + embedding IR → skeleton klas/funkcji → fine-grained edit loci.
2. **Repair:** multi-sample patchy w formacie Search/Replace (nie full-file rewrite); czasem AST canonicalize + majority vote (semantyka, nie whitespace).
3. **Patch validation:** regression subset + LLM-synthesized **reproduction tests** → filtr → ranking → submit jednego patcha.

### Co jest agent-free

- Kolejność faz, format diff, parsing AST, uruchomienie testów, ranking większościowy, budżet sample’ów.
- **Zakaz:** LLM nie wybiera kolejnego narzędzia, nie planuje ReAct, nie trzyma otwartego shella.

### Gdzie LLM jest wymuszony

- Ranking podejrzanych plików / elementów.
- Generacja kandydatów patchy.
- Generacja testów reprodukujących issue (część walidacji — model *w* slocie, nie jako orkiestrator).

### Wynik empiryczny (orientacyjnie)

- Historycznie top OSS koszt/skuteczność na SWE-bench Lite (~27–32% @ ~$0.34–0.70; później ~40%+ lite / ~50% verified z Claude 3.5). Argument: **prosty scaffold bije wiele agentów**.

**Implikacja fabryki:** dla bugfix z testami — preferuj Agentless-shaped job w CI/cell zamiast pełnego ACI.

---

## 4. gp-foundry — DOT compile, GitHub = executor

**Repo:** [thegpvc/gp-foundry](https://github.com/thegpvc/gp-foundry) (`@thegpvc/gp-foundry`).

### Model

```
harness.dot ──► parse → validate → model-check (bounded loops) → assemble → .github/workflows/*.yml
```

- Węzły = typy mechaniczne (`issue-agent`, `producer`, `pr-review`, `merge-gate`, `scheduled-agent`, …) + `role=*.md`.
- Krawędzie = eventy GitHub (`issues.opened`, `label=build`, `verdict=approve`).
- **Brak serwera orkiestracji** — stan w labels / PR / reviews / cron.
- Workflowy = artefakt (`# GENERATED … DO NOT EDIT`); drift-check w CI (`gp-foundry build --check`).

### Co jest agent-free

- Kompilator i model-checker topologii (escape do `needs_human` / `exit` obowiązkowy).
- **merge_gate** — polityka (`agents/policy/merge.yaml`: CI, size, protected paths), nie persona.
- Janitor rebase, supervisor re-drive (schedules), label throttle, least-privilege per job.
- Runtime content (role MD, policy) bez recompile; tylko zmiana DOT rekompiluje.

### Gdzie LLM jest wymuszony

- Scout / planner / builder / reviewer / fixer / retro — każdy hop = model w Actions (Claude Code OAuth itd.).
- Reviewer jest LLM → **policy gate jest non-negotiable backstop**.

### Trade-off

- Hopy w minutach (GHA), nie ms; dane między rolami = labels/komentarze.
- Altitude: **issue → PR → review → merge**. Do ciasnej choreografii multi-agent → Temporal/orkiestrator.

---

## 5. Temporal — deterministic workflow, non-deterministic activities

### Zasada (twarda)

| Warstwa | Wymóg | Zawartość |
|---------|-------|-----------|
| **Workflow** | Deterministyczny (replay) | pętle, stany, sygnały HITL, `continue-as-new` |
| **Activity** | Side-effect, zapisany w historii | LLM call, tool, git, test runner, API |

Jeśli LLM w Workflow → replay woła model ponownie → divergencja historii → korupcja stanu.

### Co jest agent-free

- Retries/backoff, timeouts, durability po crashu, parallel dispatch z partial failure, signal/update gates (approve/deny), pełna historia audytowa.
- Code Mode (harness): skrypt Python nad toolami — type-check **przed** runem; host calls nadal Activities.

### Gdzie LLM jest wymuszony

- Planowanie kolejnego kroku *wewnątrz* pętli agenta (wynik Activity steruje Workflow — OK, bo decyzja jest już w Event History).
- Tool selection / codegen / review text.

### Fabryka

Hybrid Slot (P1.3): Temporal = zewnętrzny mózg transakcji; coding agent = Activity z budżetem. OpenAI Codex production path używa Temporal — dowód skali.

---

## 6. Pure script issue→PR

Wzorzec: **orkiestracja = bash + GraphQL/`gh`**, inteligencja = jedna sesja modelu.

| Projekt | Deterministyczny szkielet | Slot LLM |
|---------|---------------------------|----------|
| **three-body-agent** | 5 workflowów GHA (implementer / fixer / merger / board sync / rollover); Projects V2 = stan | Claude Code CLI w implement/fix; merger może ważyć komentarze |
| **agent-pipeline** | Label `agent` → implement → review loop (≤3) → merge develop → promote | Claude Code Action **lub** Codex Action (config switch) |
| **Conductor** | YAML + Jinja routes; `script` steps (pytest) bez tokenów | `type: agent` per node; izolowane sesje |

### Co jest agent-free

- Priority pick, board moves, CI watch, sequential merge, concurrency „one run at a time”, timeouty, audit w Actions logs.
- W Conductor: routing i `set` steps — zero tokenów.

### Gdzie LLM jest wymuszony

- Implementacja issue → diff/PR.
- Fix CI / review comments.
- (Często) merger gdy „waży” review — **tu warto wyciąć LLM** i zostawić czyste required checks + CODEOWNERS.

**Rekomendacja:** merger i promote = czysto skryptowe; LLM tylko implement + bounded fix.

---

## 7. Policy-as-code merge gates

Cel: **merge decision bez modelu**.

### Mechanizmy

- **OPA / Conftest / Rego** na planach TF, manifestach, JSON raportach (nie na Markdown „opiniach”).
- **YAML policy** (gp-foundry merge.yaml): size caps, protected paths, required approval SHA-bound, CI green.
- **Evidence gates** (OpenAgentSecurity): diff → reguły ryzyka → wymagany evidence YAML → `oas gate` fail-closed.
- **SLSA provenance + SBOM** post-merge; pre-merge = conftest na capability manifests.
- Branch protection: required status checks; deny-overrides; `if: always()` na upload evidence.

### Co jest agent-free

- Ewaluacja polityki, exit codes, artefakty evidence, block merge.
- Path allow/deny, secret scan, „no weakened tests” (jeśli reguła deterministyczna).

### Gdzie LLM jest wymuszony (opcjonalnie, *przed* bramką)

- Adversarial review comment, risk narrative, sugestia evidence — **nie** werdykt merge.
- Anti-pattern: „LLM reviewer approved ⇒ merge” bez policy gate.

---

## 8. Sealed tests / shadow score / holdout

### Shadow Score Spec (v2)

\[
\text{Shadow Score} = \frac{\text{sealed failures}}{\text{sealed total}} \times 100
\]

Protokół sealed-envelope:

1. **Seal generation** — testy z speku *zanim* kod; inna **model family** niż implementer.
2. **Hash / vault** — SHA-256 w state; pliki poza worktree buildera.
3. **Implementation** — builder widzi tylko spek + własne testy.
4. **Validation** — disposable workspace; obie suity; score.
5. **Hardening** — tylko failure messages (nazwa, expected, actual), **nigdy** źródło sealed.

Conformance L1–L4; L4 = cross-family + disposable verify + provenance w raporcie.

### holdout / SaifCTL

- `holdout`: differential + hashed expected + out-of-band `--seal` (agent w workspace może sfałszować sidecar `.seal`).
- SaifCTL: gate (lint/types) → adversarial reviewer → **holdout tests** w Docker; regresje poprzednich feature’ów mechanicznie chronione.

### Co jest agent-free

- Hash verify, copy-in/run/delete sealed, scoring, fail threshold, provenance fields.
- Metamorphic / differential grade vs oracle.

### Gdzie LLM jest wymuszony

- Autorstwo sealed suite (i opcjonalnie open tests).
- Implementacja pod spek.
- **Nie** w graderze (jeśli score z exit codes). Uwaga: OctopusGarden używa LLM-judge satysfakcji 0–100 — **mniej deterministyczne**; na WAVE3 traktować jako anty-wzorzec orakulum, chyba że holdout YAML jest boolean.

---

## 9. PlanCompiler — ekstremum „LLM tylko w planie”

LLM wybiera węzły z **fixed registry** + parametry → 7 checków strukturalnych → kompilator składa Python z template’ów → **zero dalszych calli LLM**.

Agent-free: walidacja, topo-sort, execution.  
LLM forced: wyłącznie planning JSON.  
Limit: domena = skończona biblioteka prymitywów (nie dowolne GitHub issue). Dla fabryki: wzorzec na **ETL / data / known playbooks**, nie na greenfield feature.

---

## 10. Macierz: co zostaje agent-free vs gdzie LLM jest forced

| Warstwa fabryki | Agent-free (preferuj) | LLM forced (slot) | Unikać |
|-----------------|----------------------|-------------------|--------|
| **Intake / triage routing** | Label rules, size heuristics, keyword/ACL | Klasyfikacja „build vs plan vs needs-human” gdy spek mglisty | Agent sam nadaje sobie scope |
| **Orkiestracja / stan** | DOT→GHA, Temporal Workflow, YAML Conductor, bash FSM | — | LLM „co dalej?” jako router |
| **Lokalizacja błędu** | IR/embeddings, stack traces, `git blame` heurystyki | Hierarchical file/element pick (Agentless) | Swobodny browse całego monorepo |
| **Implementacja / patch** | Apply diff, formatters, AST validate | Generacja Search/Replace / code | Open-ended shell bez ACI |
| **Test gen** | Sealed suite z osobnej family; property/holdout generators | Reproduction tests; open unit tests buildera | Builder pisze i widzi acceptance |
| **Walidacja** | CI, sealed run, shadow score, regression | Interpretacja logów przy repair | „Ufam agentowi że tests passed” |
| **Review** | Semgrep, linters, CODEOWNERS | Komentarz jakości / security narrative | Approve = merge |
| **Merge** | Policy-as-code, required checks, SHA-bound approval | — | LLM merger „wyważa” i merge’uje |
| **Self-heal** | Rebase janitor, bounded retry counter, escalate label | Fixer na CI/review text (N≤k) | Nieskończona pętla „jeszcze raz” |
| **Memory / retro** | Indeks lekcji, retrieval deterministyczny | Ekstrakcja lekcji z merged PR | Retro zmienia topologię bez PR na DOT |

### Reguła kciuka (WAVE3)

> **Wszystko, co da się wyrazić jako exit code, hash, Rego lub krawędź grafu — zostaje agent-free. LLM tylko tam, gdzie wejście jest językiem naturalnym lub trzeba zsyntezować kod/test, którego nie ma w registry.**

---

## 11. Stack referencyjny „more deterministic dark factory”

Składanka praktyczna (nie jeden repo):

```
Spec + sealed suite (shadow L2–L4)
        │
        ▼
Deterministic orchestrator
  · gp-foundry (audit-first, zero host)  LUB
  · Temporal (durable, long missions)     LUB
  · Conductor / pure GHA scripts (proste lane’y)
        │
        ▼
Agentless-shaped coding slot
  localize → multi-sample repair → validate
  (Activity / GHA job, bounded $ / turns)
        │
        ▼
Independent verify (fresh worktree + CI)
        │
        ▼
Policy-as-code merge_gate (no LLM)
        │
        ▼
MERGED | ESCALATED | BUDGET_EXCEEDED
```

Porównanie z agent-first: patrz `STRATEGY_AGENT_FIRST.md` / WAVE wcześniejsze — tu celowo **odchudzona autonomia**.

---

## 12. Limity determinizmu (żeby nie overclaim)

1. **Treść slotu LLM nadal nondeterministyczna** — ten sam prompt ≠ ten sam patch; mitigacje: temperature↓, multi-sample+vote, structured diff, cache.
2. **Sealed gen też jest LLM** — stąd L4 cross-family; słaby spek → słaby seal.
3. **GHA-compiled graf** nie zastąpi dynamicznego subgraph discovery (gp-foundry to przyznaje).
4. **PlanCompiler** nie skaluje się na otwarte SWE-bench issues bez rozrostu registry.
5. **False-green** na holdout/SWE-bench zdarza się (patrz holdout FALSE_GREEN) — oracle ≠ prawda absolutna; golden suite + telemetria post-merge nadal potrzebne (P10.3).

---

## 13. Źródła (szybszy indeks)

### Papers / spece

| | |
|--|--|
| Agentless | https://arxiv.org/abs/2407.01489 · https://arxiv.org/pdf/2407.01489 |
| PlanCompiler | https://arxiv.org/abs/2604.13092 · https://github.com/prnvh/plancompiler |
| Shadow Score Spec | https://github.com/DUBSOpenHub/shadow-score-spec |
| O’Reilly — keep deterministic work deterministic | https://www.oreilly.com/radar/keep-deterministic-work-deterministic/ |

### GitHub — orkiestracja / pipeline

| | |
|--|--|
| gp-foundry | https://github.com/thegpvc/gp-foundry |
| Agentless | https://github.com/OpenAutoCoder/Agentless |
| microsoft/conductor | https://github.com/microsoft/conductor |
| three-body-agent | https://github.com/a7t-ai/three-body-agent |
| agent-pipeline | https://github.com/TheCraigHewitt/agent-pipeline |
| temporal-ai-agent | https://github.com/temporal-community/temporal-ai-agent |
| temporal-agent-harness | https://github.com/temporal-community/temporal-agent-harness |

### GitHub — bramki / sealed

| | |
|--|--|
| OpenAgentSecurity | https://github.com/mateaix/openagentsecurity |
| dark-factory (sealed ref) | https://github.com/DUBSOpenHub/dark-factory |
| holdout | https://github.com/brevity1swos/holdout |
| Temporal AI patterns | https://github.com/temporalio/skill-temporal-developer/blob/main/references/core/ai-patterns.md |

### Blog / docs

| | |
|--|--|
| Temporal — dynamic agents + deterministic workflows | https://temporal.io/blog/of-course-you-can-build-dynamic-ai-agents-with-temporal |
| Conductor announcement | https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/ |
| Agentless decoded | https://www.eulerfold.com/research-decoded/agentless-demystifying-software-engineering-agents |

---

## 14. One-liner dla parent / strategy

**WAVE3:** maksymalizuj powierzchnię *exit-code / Rego / compiled-graph / sealed-hash*; wpychaj LLM wyłącznie w localize·repair·(opcjonalnie review/test-gen); merge i routing zawsze agent-free. Agentless + gp-foundry/Temporal + policy gate + shadow score = kanoniczny zestaw „more deterministic factory”.
