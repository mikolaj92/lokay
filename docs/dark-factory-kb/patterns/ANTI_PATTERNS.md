# Antywzorce ciemnej fabryki oprogramowania

> Antywzorzec = powtarzalny sposób, w jaki lights-out mill **udaje** fabrykę, a produkuje limbo, ciche pominięcia albo defekty na skalę przemysłową.
> Każdy wpis: objaw → mechanizm → skutek → remedium (odsyłacz do wzorca z `PATTERNS.md`).

---

## A1. Limbo i stany zawieszenia

### A1.1 Limbo Label (`IN_PROGRESS` Forever)
**Objaw.** Issue/PR/misja wiszą w „w toku” dniami bez heartbeat, TTL ani terminalnego stanu.
**Mechanizm.** Brak jawnej maszyny stanów; status żyje w chatcie agenta lub w etykiecie bez watchdogów.
**Skutek.** Occupancy lock nigdy nie zwalnia; kolejka głoduje; ludzie myślą, że „fabryka pracuje”.
**Remedium.** P2.2 + P4.2: stany terminalne, TTL, heartbeat; po wygaśnięciu → `FAILED` lub `ESCALATED`.

### A1.2 Eternal Stuck (Waiting on Human Mid-Run)
**Objaw.** Agent pyta o decyzję w środku misji i czeka w nieskończoność.
**Mechanizm.** Projekt zakłada HITL w trakcie headless run.
**Skutek.** Hang do timeoutu lub wieczne limbo; praca równoległa zablokowana.
**Remedium.** P7.3: decyzje tylko *przed* dispatch (go/no-go) lub *po* `BLOCKED` (escalation). Mid-run = zakazane.

### A1.3 Soft-Fail / Hopeful Continue
**Objaw.** Gate nie zwrócił werdyktu → pipeline idzie dalej „na wszelki wypadek”.
**Mechanizm.** Fail-open domyślne; timeout traktowany jako PASS.
**Skutek.** Merge bez audytu, „zielone” PR bez testów.
**Remedium.** P4.1: brak werdyktu = FAIL.

### A1.4 Retry Storm Without Budget
**Objaw.** Agent w pętli naprawia ten sam błąd setki razy.
**Mechanizm.** Self-repair bez limitu prób/kosztu/czasu.
**Skutek.** Spalanie tokenów, flapping CI, lock starvation.
**Remedium.** P4.3 + P8.1: bounded repair; potem escalate z evidence.

### A1.5 Zombie Session
**Objaw.** Proces agenta żyje, ale nie robi postępu (idle pod, martwy heartbeat).
**Mechanizm.** Brak liveness probe / occupancy lease expiry.
**Skutek.** Zajęte worktree i pody; katalog occupancy kłamie.
**Remedium.** P6.1: lease + TTL + cleanup.

---

## A2. Ciche pominięcia i fałszywe dostawy

### A2.1 Silent PR Omission
**Objaw.** Misja raportuje „done”, ale nie ma PR / PR jest w złym repo / draft nigdy nie opublikowany.
**Mechanizm.** Sukces mierzony „agent finished chat”, nie artefaktem handoff.
**Skutek.** Praca znika; metryki throughputu kłamią.
**Remedium.** P3.5: jedyny deliverable = PR (lub stack) z linkiem do issue; brak PR = `FAILED`.

### A2.2 Local-Green Lie
**Objaw.** Agent merguje lub zamyka issue na podstawie lokalnych testów.
**Mechanizm.** Local loop mylony z CI jako autorytetem.
**Skutek.** Regresje w main; flaky ukryte w środowisku agenta.
**Remedium.** P5.1–P5.2: CI + niezależna re-weryfikacja obowiązkowe.

### A2.3 Claimed Tests Without Re-run
**Objaw.** Opis PR: „all tests passed” — nikt nie odpalił suite na świeżym checkout.
**Mechanizm.** Zaufanie do narracji modelu.
**Skutek.** Symptom patches, osłabione asercje, wycięte testy.
**Remedium.** P5.2 + fail-closed audit na „weakened validation”.

### A2.4 Scope Smuggling
**Objaw.** PR naprawia bug i „przy okazji” refaktoruje pół systemu / zmienia CI / secrets.
**Mechanizm.** Brak file-scope w unit of work; agent optymalizuje „kompletność”.
**Skutek.** Niemożliwy review (nawet agentowy); blast radius.
**Remedium.** Deklarowany scope + audit fail-closed (P4.1, Warden-style).

### A2.5 Evaluator Contamination (Train/Test Leak)
**Objaw.** Implementer widzi holdout scenarios albo ewaluator i koder dzielą kontekst.
**Mechanizm.** Brak separacji train/test.
**Skutek.** Overfit do scenariuszy; L5 staje się teatrem.
**Remedium.** P3.2 + P5.3: izolowany ewaluator, holdouty niewidoczne.

### A2.6 Merge Without Evidence Bundle
**Objaw.** Auto-merge bez policy_trace, model id, spek hash, logów gates.
**Mechanizm.** Lights-out mylone z „bez audytu”.
**Skutek.** Niemożliwa odpowiedzialność; regulated abort.
**Remedium.** P9.5 + P10.4.

---

## A3. Orkiestracja i współbieżność

### A3.1 Chat-as-Orchestrator
**Objaw.** Długi prompt „zrób cały SDLC” w jednej sesji ReAct.
**Mechanizm.** Brak zewnętrznego FSM/Temporal; stan tylko w context window.
**Skutek.** Utrata stanu, niedeterminizm, brak retry granularnego.
**Remedium.** P1.3 + P2.1: hybrid slots + durable workflow.

### A3.2 Parallel Agents, Shared Dirty Tree
**Objaw.** Dwóch agentów w jednym working directory.
**Mechanizm.** „Szybciej” bez worktree.
**Skutek.** Race na plikach, popsute diffy, nieodtwarzalne błędy.
**Remedium.** P6.3: worktree-per-task + occupancy.

### A3.3 Lock-Free Multi-Agent Hope
**Objaw.** „Agenty się dogadają” bez lease na ścieżki/issue.
**Skutek.** Duplicate PR, konflikty, thrashing.
**Remedium.** P6.1–P6.2.

### A3.4 Concurrent Push to Deploy Refs
**Objaw.** Każdy agent pushuje na main/release po swoim green.
**Mechanizm.** Brak merge-train / runner lock.
**Skutek.** Semantic conflicts, niestabilny main.
**Remedium.** P6.4: enqueue → pojedynczy runner → atomic push.

### A3.5 Multi-Repo Single Session
**Objaw.** Jedna sesja z montażem dwóch repo „żeby było wygodniej”.
**Mechanizm.** Ignorowanie scoped AGENTS.md / konwencji per root.
**Skutek.** Agent działa w drugim repo bez kontekstu; cross-cutting bugs.
**Remedium.** P7.2: osobny proces per repo + koordynator.

---

## A4. Jakość, harness, model

### A4.1 Autocomplete Labeled as Factory
**Objaw.** Marketing „software factory”, a w praktyce L2/L3 z człowiekiem na każdym diffie.
**Mechanizm.** Inflacja terminu.
**Skutek.** Fałszywe oczekiwania; brak inwestycji w oracle/harness.
**Remedium.** P0.2: nazywaj poziom po imieniu; L5 = brak human code review.

### A4.2 Weak Oracle Acceleration
**Objaw.** Włączenie auto-merge na suite, które już dziś przepuszcza bad code.
**Mechanizm.** L5 na słabym teście.
**Skutek.** Fabryka defektów × throughput.
**Remedium.** Ostrzeżenie P0.1: najpierw utwardź oracle (P5, P9).

### A4.3 Model Upgrade Without Golden Gate
**Objaw.** Zmiana modelu/promptu w produkcji bez internal bench.
**Skutek.** Ciche regresje resolve rate / stylu / bezpieczeństwa.
**Remedium.** P9.2–P9.3: golden issues + Pareto routing.

### A4.4 Raw Shell as Only ACI
**Objaw.** Agent dostaje `bash` bez guardrailów edycji/search.
**Skutek.** Niższy resolve rate, `rm -rf`, wycieki sekretów.
**Remedium.** P1.4 + sandbox (P3.3).

### A4.5 Infinite Context as Memory
**Objaw.** Cała historia misji w jednym oknie kontekstu.
**Skutek.** Drift, koszt, utrata sygnału; „zapomniane” constraints.
**Remedium.** P8.2: strukturalna pamięć + krytyki epizodyczne; stan w orchestratorze.

### A4.6 Autonomy Without Promotion Gates
**Objaw.** Nowy agent od razu z prawem merge do prod.
**Mechanizm.** Flaga „full agency” bez dowodów.
**Skutek.** Incydenty; utrata zaufania do całego fleetu.
**Remedium.** P9.4: maturity + demotion.

---

## A5. Ludzie, governance, ekonomia

### A5.1 Human Disappears (Not Moves Up)
**Objaw.** Usunięto review, nie dodano speku, holdoutów, Owner of policy, on-call AgentOps.
**Skutek.** Nikt nie odpowiada; „trusted by whom?”.
**Remedium.** P10.3–P10.4.

### A5.2 Token Burn Without Metering
**Objaw.** Brak budżetu per misja / per repo / per dzień.
**Skutek.** Koszt liniowy z throughputem pożera gains; runaway loops.
**Remedium.** P4.3 + budget gates w harnessie; metryki jak cloud spend.

### A5.3 Regulated Path Forced to L5
**Objaw.** Billing/funds/PII path bez human sign-off, mimo wymogów.
**Skutek.** Legal abort; reputacja.
**Remedium.** P0.2 / P10.1: autonomia per *code path*, nie per zespół.

### A5.4 Metrics Theater
**Objaw.** KPI = „liczba PR agentów”, nie merge rate, revert rate, escape defects, override rate ewaluatora.
**Skutek.** Optymalizacja pod spam PR.
**Remedium.** Mierz: % merged, time-to-merge, CI flake attribution, post-merge incidents, evaluator↔human alignment.

### A5.5 Silent Supersede / Duplicate Work
**Objaw.** Nowy agent startuje to samo issue bez zamknięcia poprzedniego lease.
**Skutek.** Dwa PR, konflikt occupancy, strata pracy.
**Remedium.** P6.1: jawne supersede policy + close poprzedniej misji.

---

## A6. Antywzorce nazwane „etykietami limbo” (cheat-sheet)

| Etykieta / stan | Co zwykle oznacza naprawdę | Poprawny terminal |
|-----------------|----------------------------|-------------------|
| `in_progress` &gt; TTL | zombie / forgotten | `FAILED` / `ESCALATED` |
| `waiting_for_input` w headless | eternal stuck | nie używać; `BLOCKED`→escalation |
| `done` bez URL PR | silent PR omission | `FAILED` |
| `tests_passed` (local only) | local-green lie | czekaj na CI |
| `merged` bez evidence | ungoverned dark | rollback policy |
| `needs_review` bez assignee/SLA | soft limbo | TTL → escalate |
| `repairing` bez licznika | retry storm | budget → escalate |

---

## Priorytet walki (kolejność gaszenia)

1. **Silent PR omission** i **limbo labels** — psują wiarygodność metryk.  
2. **Fail-open gates** i **local-green lie** — wpuszczają defekty.  
3. **Shared dirty tree / lock-free** — psują paralelizm.  
4. **Evaluator leak** i **weak oracle** — unieważniają L5.  
5. **Chat-as-orchestrator** i **retry storm** — koszt i niestabilność.  
6. **Metrics theater** i **human disappears** — governance debt.

Zobacz: [PATTERNS.md](./PATTERNS.md), [SOURCES.md](./SOURCES.md).
