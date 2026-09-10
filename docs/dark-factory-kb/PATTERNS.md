# Katalog wzorców: ciemna fabryka oprogramowania (Dark AI Software Factory)

> **Definicja robocza.** *Ciemna fabryka* (lights-out / human-out-of-loop coding mill) to model operacyjny, w którym agenty AI realizują pełny cykl: triage → implementacja → weryfikacja → PR → merge (i często deploy), bez człowieka piszącego ani recenzującego kod. Człowiek działa **nad** kodem: specyfikacje, scenariusze akceptacyjne, polityki, harness i telemetria produkcyjna.
>
> Metafora pochodzi z produkcji: FANUC Yamanashi (od 1981) — linia robotów budujących roboty, światła zgaszone, bo na hali nie ma ludzi. W softwarze: *specs in → working software out*, nikt nie czyta diffów (Shapiro L5, StrongDM manifesto 2026).

Dokument zbiera **abstrakcyjne wzorce** (nie produkty). Każdy wzorzec: problem → siły → rozwiązanie → konsekwencje → warianty.

---

## P0. Metafora i drabina autonomii

### P0.1 Dark Factory (Lights-Out Software Mill)
**Problem.** Recenzja ludzka staje się wąskim gardłem, gdy agenty generują 10–100× więcej diffów.
**Rozwiązanie.** Przenieść człowieka na warstwę intencji (spec + holdout scenarios + policy). Kod i review kodu są w pełni agentowe. Weryfikacja: stacked gates + izolowany ewaluator + telemetria.
**Konsekwencje.** Throughput rośnie; jakość = jakość orakulum testowego. Słaby oracle → fabryka defektów.

### P0.2 Drabina Shapiro (L0–L5)
| Poziom | Rola człowieka | Jednostka pracy |
|--------|----------------|-----------------|
| L0 Spicy Autocomplete | autor każdej linijki | fragment |
| L1 Coding Intern | deleguje boilerplate | funkcja |
| L2 Junior | para, czyta każdą linię | multi-file |
| L3 Developer | recenzent concurrent | feature |
| L4 Engineering Team | autor speku + harness | spec + suite |
| L5 Dark Factory | projektant fabryki | cel w języku naturalnym |

**Wzór:** nie skacz do L5; wspinaj się przez harness i oracle.

### P0.3 Agent = Model + Harness (Böckeler / Kropp)
Model bez harnessu to chatbot. Harness = narzędzia, sandbox, haki, pamięć, ewaluatory, limity budżetu, polityki. Fabryka = **model + harness + orkiestracja + katalog repo + gates**.

---

## P1. Deterministyczny harness vs agent LLM z narzędziami

### P1.1 Deterministic Pipeline (Agentless-style)
**Problem.** Pełna autonomia ReAct jest droga, niestabilna i trudna do audytu.
**Rozwiązanie.** Stała maszyna faz: lokalizacja → naprawa → walidacja. LLM tylko w wyznaczonych slotach (np. generowanie patcha); routing i stany są deterministyczne.
**Kiedy.** Zadania o znanym kształcie (bugfix z testami), wymagania compliance, kosztowo wrażliwe fleety.
**Trade-off.** Mniejsza elastyczność na niejednoznaczne feature'y.

### P1.2 Tool-Using LLM Agent (SWE-agent / OpenHands-style)
**Problem.** Zadania wymagają eksploracji, nawigacji po repo, iteracji na podstawie obserwacji.
**Rozwiązanie.** Pętla ReAct + ACI (agent–computer interface): edytory z guardrailami, search, shell, test runner. Agent decyduje o kolejności narzędzi.
**Kiedy.** Otwarte issue'y, nieznane codebase'y, research-y.
**Trade-off.** Nieokreśloność, ryzyko limbo, wyższy koszt tokenów.

### P1.3 Hybrid Slot Architecture
**Wzór kanoniczny fabryki:** zewnętrzny **deterministyczny** graf (Temporal / state machine) + wewnętrzne **sloty agentowe** (LLM + tools) z twardymi timeoutami, budżetami i kryteriami wyjścia. Orkiestrator nigdy nie „myśli”; agent nigdy nie „zarządza transakcją merge”.

### P1.4 Purpose-Built ACI
Nie dawaj surowego shella jako jedynego UI. Specjalizowane komendy (view/edit z syntax check, search_dir, run_tests) podnoszą resolve rate i zmniejszają katastroficzne akcje.

---

## P2. Orkiestracja: graf / maszyna stanów

### P2.1 Durable Workflow Orchestration (Temporal-class)
**Problem.** Długie misje (godziny–dni) giną przy restarcie procesu; human-in-the-loop nie może trzymać otwartego procesu.
**Rozwiązanie.** Workflow z checkpointami: każdy węzeł = Activity z retry/timeout. Interrupt = trwałe wstrzymanie bez spalania CPU. Continue-as-new + cache wyników węzłów.
**Wariant 2026:** LangGraph (definicja agenta) + Temporal (durable execution) — rozdział ról: framework vs orchestrator.

### P2.2 StateGraph / Explicit FSM
Jawne stany: `TRIAGED → PLANNED → IMPLEMENTING → VERIFYING → PR_OPEN → CI_WATCH → REPAIR → MERGE_READY → MERGED | FAILED | ESCALATED`. Przejścia tylko przez bramki polityk. Zakaz „ukrytych” stanów w promptach.

### P2.3 Nested Control Loops (Miniforge-style)
Cztery pętle:
1. **Inner quality** — lint/test/gate na każdym kroku.
2. **Team agents** — planner / implementer / tester / reviewer.
3. **PR monitor** — po otwarciu PR: CI, komentarze, rebase.
4. **Meta-governance** — budżet, konflikty, halt fabryki.

Meta-agent może zatrzymać floor; nie tylko „doradzać”.

### P2.4 Mission Decomposition / Parallel Tracks
Duże cele → DAG równoległych torów z izolowanymi worktree i budżetami per-task. Scalanie przez merge-train / stacked PRs, nie jeden monolityczny diff.

---

## P3. Linia produkcyjna: triage → implement → verify → PR → merge

### P3.1 Intake & Triage Gate
Wejście: issue tracker / Linear / Jira / webhook. Triage klasyfikuje: typ, ryzyko, repo, szacunek, czy zadanie jest *agent-ready* (spec, testy, brak sekretów). Fail-closed: niejasne → `NEEDS_HUMAN_SPEC`, nie startuj implementacji.

### P3.2 Spec-First / NLSpec Contract
Zamiast chatu: wersjonowany dokument (Goal, Constraints, Interfaces, Non-goals) + **holdout scenarios** niewidoczne dla kodera. Train/test separation jak w ML — rdzeń L5.

### P3.3 Isolated Execution Cell
Jednostka pracy = sandbox (kontener/VM/pod) + git worktree + limity sieci/CPU/tokenów. Żadnego współdzielonego dirty working tree między agentami.

### P3.4 Implement → Local Verify → CI Verify (dwustopniowa weryfikacja)
1. **Local:** szybkie unit/lint w komórce (feedback w sekundach).
2. **CI:** pełny pipeline na PR (prawda organizacyjna).
Agent nie ufa własnemu „tests passed”; CI i niezależny ewaluator są autorytetem.

### P3.5 PR as Handoff Artifact
Jedyny legalny produkt pośredni = PR (lub stack PR). Session transcript nie jest deliverable. Opis PR = dowód: link do issue, lista gates, budżet, hash speku.

### P3.6 Feedback Resume Loop
CI fail / review comment / conflict → automatyczne wznowienie agenta z kontekstem błędu (bounded retries). Sukces → squash-merge + close issue. To jest „taśma”, nie one-shot.

### P3.7 Stacked / Ordered Delivery
Duże zmiany → stack małych PR (Devin-style) lub merge-train z re-weryfikacją po każdym merge. Decompozycja jest domyślna, nie dyscyplina ręczna.

### P3.8 Spectrum of Autonomy (Factory.ai Missions)
Nie wszystko L5: skills (krótkie), automations (cykliczne), remote computers (długie), missions (multi-agent dni). Dobór poziomu = wrażliwość danych × jasność zadania × gotowość agentowa.

---

## P4. Fail-closed vs limbo

### P4.1 Fail-Closed Gates
Brak werdyktu = **FAIL**. Polityki YAML/deterministyczne (bez LLM w ewaluatorze bramek). Deny-overrides. Przykłady: secrets scan, scope violation, weakened tests, brak `AUDIT: PASS`.

### P4.2 Explicit Terminal States
Każda misja kończy się jednym z: `MERGED`, `FAILED`, `ESCALATED`, `BUDGET_EXCEEDED`, `SUPERSEDED`. Zakaz wiecznego `IN_PROGRESS` bez heartbeat i TTL.

### P4.3 Bounded Repair Budget
Naprawy mają twardy limit (N prób / $ / minuty). Po wyczerpaniu → escalate z evidence bundle, nie kolejna „jeszcze jedna próba”.

### P4.4 Halt Authority (Distributed)
Meta-agenty / policy daemon mogą zatrzymać floor (conflict detector, resource manager). Halt jest pierwszoplanowy względem throughputu.

---

## P5. Local tests vs CI

### P5.1 Fast Inner Loop, Authoritative Outer Loop
Local = optymalizacja latency. CI = kontrakt jakości organizacji (flaky quarantine, required checks, environment parity).
**Anti-pattern:** merge na podstawie local green przy czerwonym CI.

### P5.2 Independent Re-verification
Claim agenta „all tests pass” nigdy nie jest zaufany. Świeży checkout / worktree + ponowne uruchomienie suite (Warden-style).

### P5.3 Holdout Evaluator Separation
Ewaluator (agent lub harness) ocenia scenariusze, których implementer nie widział. Align evaluator↔human przed auto-merge (np. 20–30 PR, override &lt;10%).

### P5.4 Eval Harness as Factory Mirror (SWE-bench-class)
Konteneryzowana ewaluacja: apply patch → run tests → report.json. Fabryka produkcyjna powinna mieć **wewnętrzny** harness regresji (golden issues) analogiczny do SWE-bench Verified/Lite — inaczej nie wiesz, czy upgrade modelu cofnął jakość.

---

## P6. Occupancy, locki, izolacja

### P6.1 Occupancy Lock / Lease
Jednostka pracy (issue, ścieżki plików, branch) ma lease z TTL i heartbeat. Drugi agent nie wchodzi na zajęte ścieżki bez supersede policy.

### P6.2 Shared Lock Store Outside Working Tree
Locki w `.git` common-dir / zewnętrznym store (MCP locks), żeby worktree nie commitowały locków i wszystkie worktree tego samego repo je widziały.

### P6.3 Worktree-per-Task
Jeden agent = jeden worktree = jeden branch. Paralelizm bez dirty conflicts. Idle cleanup dla podów/komórek.

### P6.4 Runner Lock on Merge Train
Agenty **enqueue** branchy; jeden runner scala FIFO, odpala gates na całym pociągu, atomic push. Żadnych równoległych pushy na deploy refs.

### P6.5 Machine-Wide Concurrency Cap (Multi-Repo)
Hub: wiele repo, jeden globalny limit równoległych ciężkich gates (np. jeden engine build naraz). Paralelni agenci ≠ równoległe destrukcyjne CI.

---

## P7. Multi-repo catalogs

### P7.1 Repo Catalog + Agent-Readiness Score
Katalog: URL, default branch, AGENTS.md, required checks, secret policy, language toolchain, „czy agent-ready”. Triage routinguje tylko do gotowych repo.

### P7.2 Per-Repo Context Isolation
Nie dawaj jednemu session dostępu do dwóch rootów „przy okazji”. Konwencje/spec są scoped do roota — osobny proces per repo, koordynator nad nimi.

### P7.3 Cross-Repo Go/No-Go Gate
Zmiany wielorepozytoryjne: plan + jawne go/no-go przed dispatch. Mid-run pytania → hang; decyzje tylko przed lub po `BLOCKED`.

### P7.4 Policy Inheritance (Deny-Additive)
Daemon policy + repo-local additive denies. Sklonowane repo nie może osłabić globalnych deny bez operator approval.

---

## P8. Self-repair

### P8.1 Closed-Loop Repair on Observable Failure
Źródła sygnału: local test fail, CI, review comments, runtime alerts. Resume z failure context; nie restart od zera bez powodu.

### P8.2 Reflexion / Episodic Critique
Po nieudanej próbie: werbalna krytyka → conditioning kolejnej próby (bounded). Pamięć epizodyczna per-task, nie nieskończony chat.

### P8.3 Self-Healing CI Agents (Managed Fleet)
Osobna klasa managed agents: flaky quarantine, dependency bumps, conflict rebase (Uber Software Factory). Inny model/Pareto niż feature implementer.

### P8.4 Post-Merge Monitor
Po merge: agent obserwuje review late comments / canary metrics; rollback lub hotfix w osobnej misji. Delivery ≠ koniec pętli.

---

## P9. Evaluation harnesses

### P9.1 Containerized Patch Eval (SWE-bench Pattern)
Izolowany Docker, apply unified diff, run repo tests, cache po `(run_id, instance_id)`, artefakty: report.json, test_output, patch.diff. **Zmiana predicji wymaga nowego run_id.**

### P9.2 Golden Issue Suite (Internal Bench)
Własny zestaw issue'ów z holdoutami; gate na promocję modelu/promptu/harnessu. Bez tego „upgrade” jest loterią.

### P9.3 Pareto Model Routing
Per klasa zadań: benchmark → wybór modelu na krzywej jakość/koszt (Uber). Fleet specjalizowanych agentów &gt; jeden terminal session na tysiące inżynierów.

### P9.4 Agent Maturity / Promotion Gates
Autonomia jest **zarabiana** (Intern→Principal / AWS scoping). Continuous verification + demotion przy incydentach. L5 nie jest flagą w konfiguracji.

### P9.5 Evidence Bundles
Każda decyzja (merge, halt, escalate) produkuje audytowalny pakiet: spek hash, logi gates, token cost, model id, policy_trace. Lights-out ≠ brak pokwitowań (governed dark factory).

---

## P10. Dojrzałość fabryki i warstwy operacyjne

### P10.1 Autonomy Maturity Model (Factory.ai-class)
Filary + poziomy gotowości organizacji; DMASI / stopniowe wdrażanie. Żadna org nie startuje w pełnym L5.

### P10.2 Four-Layer Agent Session Stack (Uber-class)
Sesje agentów w warstwach (lokalne → managed → fleet → platform). Optymalizacja kosztu i jakości per warstwa; przejście workloadów do managed environments.

### P10.3 Production Telemetry as Primary Reviewer
Gdy nikt nie czyta diffów, AgentOps / error budgets / domain metrics są recenzentem. Canary + auto-rollback = ostatnia bramka.

### P10.4 Human-Above-Code Accountability
Odpowiedzialność: autor speku, właściciel polityk, operator produkcji — nie „model”. Regulated paths mogą pozostać L3/L4 przy L5 na narzędziach wewnętrznych.

---

## Mapa zależności (skrót)

```
Spec + Holdout ──► Deterministic Orchestrator ──► Agent Slots (ACI)
                           │
              Occupancy / Worktree / Locks
                           │
              Local Verify ──► PR ──► CI / Independent Eval
                           │
              Fail-Closed Gates ──► Merge Train / Stack
                           │
              Telemetry / Self-Repair / Evidence
```

---

## Top 12 wzorców (priorytet wdrożeniowy)

1. **Hybrid Slot Architecture** (P1.3) — deterministyczny graf + LLM w slotach  
2. **Fail-Closed Explicit Terminals** (P4.1–P4.2)  
3. **Spec-First + Holdout Evaluator** (P3.2, P5.3)  
4. **Isolated Execution Cell / Worktree-per-Task** (P3.3, P6.3)  
5. **PR as Sole Handoff + Feedback Resume** (P3.5–P3.6)  
6. **Local≠CI Dual Verification** (P5.1–P5.2)  
7. **Occupancy Leases + Runner Lock** (P6.1, P6.4)  
8. **Nested Control Loops + Halt Authority** (P2.3, P4.4)  
9. **Repo Catalog + Per-Repo Isolation** (P7.1–P7.2)  
10. **Bounded Self-Repair** (P8.1, P4.3)  
11. **Internal Eval Harness / Golden Issues** (P9.1–P9.2)  
12. **Evidence Bundles + Telemetry-as-Reviewer** (P9.5, P10.3)

Zobacz też: [ANTI_PATTERNS.md](./ANTI_PATTERNS.md), [SOURCES.md](./SOURCES.md).
