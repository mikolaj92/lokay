# WAVE2 — Recursive / self-similar agent harness patterns

Zebrane 2026-09-10. Fala researchu: rekurencyjni plannerzy, handoff-only workerzy, ouroboros/ACE/DGM, antykruche multi-agent coding.
Powiązane: [../CURSOR_SELF_DRIVING.md](../CURSOR_SELF_DRIVING.md), [../MAZUR_AUTONOM.md](../MAZUR_AUTONOM.md), [../STRATEGY_AGENT_FIRST.md](../STRATEGY_AGENT_FIRST.md).

---

## Archetypy (mapa)

| Archetyp | Jednostka rekurencji | Co wraca w górę | Deterministyka gdzie? |
|----------|----------------------|-----------------|------------------------|
| **A. Recursive planner–worker** (Cursor) | Subplanner = ten sam rodzaj co root | Handoff (done + concerns + deviations) | Spawn/wait/state w skrypcie (`plan.json` / `state.json`); planner nie koduje |
| **B. Handoff-only workers** | Worker = izolowana kopia repo, zero peer chat | Jeden raport do właściciela scope | Isolacja worktree/branch; merge jako osobny task |
| **C. Recursive Agent Harness (RAH)** | Pełny harness (tools + FS + plan), nie bare LLM | stdout / shared output file | Parent **pisze skrypt**, który spawnuje N harnessy (omija limit tool-call) |
| **D. Recursive Language Model (RLM)** | Bare model call w REPL | Wynik sub-query w env | Kontext jako zmienna; rekurencja = `rlm_query` w kodzie |
| **E. Nested control loops** | Pętla w pętli (quality → team → PR → meta) | Gate / verdict na każdej warstwie | Zewnętrzna FSM; wewnątrz sloty agentowe |
| **F. Self-improve / ouroboros** | Agent edytuje własny harness/prompt/tools | Reviewed commit → nowy runtime | Gate ewaluacji (benchmark / review) przed merge core |
| **G. ACE (context playbook)** | Generator → Reflector → Curator | Delta bullets do playbooka | Merge delt **bez LLM** (deterministyczny curator merge) |
| **H. Anti-fragile fleet** | Failure jednego agenta ≠ halt systemu | Recovery przez innego / respawn / split | Slack error rate + okresowy green-branch; brak global lock |

---

## 1. Cursor — self-driving recursive planners

**Źródła**
- Blog: https://cursor.com/blog/self-driving-codebases (Wilson Lin, Feb 2026)
- Plugin OSS: https://github.com/cursor/plugins/tree/main/orchestrate
- Skill: https://github.com/cursor/plugins/blob/main/orchestrate/skills/orchestrate/SKILL.md
- SDK: https://cursor.com/blog/typescript-sdk
- Omówienia: https://taeho.io/en/reading/cursor-the-journey-toward-self-driving-codebases_18048 · https://akillness.github.io/posts/self-driving-codebases/

**Archetyp A+B+H.** Iteracje odrzucone → final:

1. Self-coordination (shared lock) — **padło** (lock hell, unikanie dużych tasków).
2. Planner → Executor → Workers + Judge — **sztywny**, bottleneck najwolniejszego.
3. Continuous executor (plan+spawn+merge w jednym) — **pathologie** (sleep, premature done, za dużo ról).
4. **Wygrało:** root planner → rekurencyjne subplannery → izolowani workerzy + handoff w górę. Integrator centralny usunięty jako red-tape.

**Kontrakty**
- Planner **nie koduje**; publikuje taski w `plan.json`.
- Worker nie zna siblingów; własna kopia repo; jeden handoff.
- Subplanner = recursive planner (ten sam protokół, węższy scope).
- Skrypt (`cli.ts`) trzyma spawn/wait — „long-running agent loops drift; a script with a JSON state file keeps its footing.”

**Anti-fragile (wprost z bloga):** scale ↑ → P(failure) ↑; system musi znosić pad workera i pozwalać innym odzyskać / spróbować inaczej. Świadomy slack error rate + green-branch fixup zamiast 100% green na każdy commit.

---

## 2. Mazur-like autonomy (soczewka, nie kod)

**Źródła**
- http://autonom.edu.pl · Wikipedia Marian Mazur
- Mapowanie: [../MAZUR_AUTONOM.md](../MAZUR_AUTONOM.md)

**Archetyp (analogia):** homeostat = zdolność **zachowania** sterowania (freshness, bounded retry, re-drive, handoff do korelatora), nie tylko jednorazowy efekt.

| Mazur | Harness |
|-------|---------|
| Steruje sobą | Root planner posiada cel i planuje dalej po handoffach |
| Homeostat | Anti-fragile, freshness, recovery |
| Korelator | Handoff → planner → nowe taski |
| Nie „jedno pudełko ról” | Continuous executor padł od przeładowania ról |

Nie jest przepisem na LangGraph; mówi: harness musi **zachowywać autonomię**, nie tylko odpalać kroki.

---

## 3. RAH — Recursive Agent Harnesses (paper)

**Źródła**
- Paper: https://arxiv.org/abs/2606.13643 · HTML https://arxiv.org/html/2606.13643v1
- Pattern catalog: https://agentpatterns.ai/patterns/agent-design/recursive-agent-harnesses/
- Blog (dynamic workflows): https://www.alexfeel.info/blog/dynamic-workflows-when-the-agent-writes-its-own-harness/

**Archetyp C.** Most między RLM (rekurencja nad bare model) a produkcyjnymi coding agentami (Anthropic dynamic workflows): jednostką jest **pełny harness** (FS, execute, plan, własny kontekst). Parent generuje executable script → parallel `Task()` / subagent harnesses; omija per-turn tool-call limits.

Kiedy **nie** (z agentpatterns + Anthropic multi-agent retrospective): coupled coding na shared naming/types; brak leaf-level verification signal; parent racjonalizuje słabe wyniki.

---

## 4. RLM — Recursive Language Models

**Źródła**
- Paper: https://arxiv.org/abs/2512.24601 · https://arxiv.org/html/2512.24601
- Blog: https://alexzhang13.github.io/blog/2025/rlm/
- Official: https://github.com/alexzhang13/rlm
- Ports: https://github.com/grishahq/recursive-llm · https://github.com/viplismism/rlm-cli
- HALO (RLM-based agent opt): https://github.com/context-labs/halo

**Archetyp D.** Kontext = zmienna w REPL; model pisze kod, który peeka / partition / `rlm_query`. To **nie** jest coding-mill planner–worker, ale ten sam ruch: rekurencja jako jednostka skalowania kontekstu zamiast jednego okna.

RAH = RLM + tools/FS/planning jako recursive unit.

---

## 5. Ouroboros / self-improve harness

**Źródła (kilka linii produktowych o tej samej nazwie)**
- Paper (reviewed core evolution): https://arxiv.org/html/2608.08311 · https://arxiv.org/pdf/2608.08311 · https://ouroboros-agent.ai/
- RSI harness (Bun/TS): https://github.com/secondorderai/ouroboros
- Agent OS / Double Diamond evolve: https://github.com/Q00/ouroboros
- Wcześniejszy wpis w SOURCES: https://github.com/Tanush1912/ouroboros

**Archetyp F.** Dwa tryby (paper):
1. **Recursive free evolution** — improve = task; completion może zaplanować kolejny cykl.
2. **Experience-driven core evolution** — ordinary work ujawnia error classes → maintenance pod tym samym reviewed commit gate.

Wzorzec: launcher/supervisor oddzielony od mutable agent repo; self-mod przechodzi przez gate, potem staje się runtime.

---

## 6. ACE — Agentic Context Engineering

**Źródła**
- Paper: https://arxiv.org/abs/2510.04618 · https://arxiv.org/html/2510.04618 (ICLR 2026)
- Site: https://ace-agent.github.io/
- Official: https://github.com/ace-agent/ace
- Faithful reimpl: https://github.com/rrahimi-uci/agentic-context-engineering
- SambaNova announce: https://sambanova.ai/blog/ace-open-sourced-on-github

**Archetyp G.** Generator (trajektorie) → Reflector (insights) → Curator (delta ADD/UPDATE/REMOVE) → **deterministyczny merge** playbooka. Grow-and-refine przeciw brevity bias / context collapse.

Ważne dla mills: self-improve **kontekstu/strategii**, niekoniecznie kodu harnessu; curator merge = miejsce na „wycinanie w deterministykę”.

---

## 7. Nested loops & DAG orchestrators (GitHub)

| Repo | URL | Archetyp | Notatka |
|------|-----|----------|---------|
| Cursor orchestrate | https://github.com/cursor/plugins/tree/main/orchestrate | A+B | plan.json + handoffs/ + recursive subplanner |
| lindy-orchestrator | https://github.com/eddieran/lindy-orchestrator | E+B | Planner→Generator→Evaluator; DAG; worktree isolation; QA gates |
| dagain | https://github.com/knot0-com/dagain | E | SQLite work graph; plan/task/verify/integrate; fresh context z DB |
| task-orchestrator | https://github.com/mrweixy/task-orchestrator | E | Explicit TaskGraph; write-set isolation; acceptance gates |
| Grindstone | https://github.com/shbhmydv/Grindstone | A+B+E | Stateless planner per epoch; free-form `handoff.md`; critic triage; FSM |
| gp-foundry | https://github.com/thegpvc/gp-foundry | E | Skompilowany graf DOT + merge_gate (patrz SOURCES) |
| OpenHands | https://github.com/All-Hands-AI/OpenHands | B-ish | Runtime + delegation; mniej „self-similar planner tree” |
| SWE-agent | https://github.com/SWE-agent/SWE-agent | single harness | ACI; nie recursive mill |
| Agentless | https://github.com/OpenAutoCoder/Agentless (typ.) | **graf-first** | Fazy deterministyczne; LLM w slotach — antyteza swarm |

Nested loops (PATTERNS P2.3): inner quality → team agents → PR monitor → meta-governance. Meta może **halt** floor, nie tylko doradzać.

---

## 8. Self-referential / open-ended evolution (papers + code)

| System | Paper | Code | Idea |
|--------|-------|------|------|
| **Darwin Gödel Machine (DGM)** | https://arxiv.org/abs/2505.22954 · HTML https://arxiv.org/html/2505.22954v3 | https://github.com/jennyzzt/dgm | Archive agentów; self-modify code; eval na SWE-bench/Polyglot |
| **Gödel Agent** | https://arxiv.org/abs/2410.04444 · ACL https://aclanthology.org/2025.acl-long.1354/ | https://github.com/Arvid-pku/Godel_Agent | Self-referential rewrite policy + meta-learning |
| **Meta n** | https://arxiv.org/html/2608.24735 | https://github.com/minnesotanlp/meta-n | Stałe Ω; rekurencja na **input** (głębia emerguje); unika destabilizacji self-edit |
| **Ouroboros** | https://arxiv.org/html/2608.08311 | secondorderai / Q00 (wyżej) | Reviewed core evolution w live harness |
| MetaAI RSI evidence | https://arxiv.org/html/2606.09663 | — | Mapowanie DGM/STOP/Gödel/ADAS jako evidence |

---

## 9. Contradiction note: „start with deterministic graph” vs „start with agents”

To jest **napięcie kolejności budowy**, nie sprzeczność o dojrzałym celu.

### Teza graf-first (dojrzały cel / compliance / koszt)

- Lokay archetype: *„Graf jest wartością, ponieważ graf jest procesem. Węzły są wymiennymi wykonawcami.”*
- Agentless / Dual-Engine (Spine=code, Brain=LLM): https://www.alphapebble.io/playbooks/dual-engine-architecture — LLM **nie** zarządza własną pętlą stanu.
- Harness vs framework: https://winder.ai/ai-agent-harness-comparison/ — LangGraph gdy jawny branching; plain loop gdy single agent.
- RAH/agentpatterns: nie używaj recursive harness jako default; potrzebujesz verification signal i partitionable work.
- Cognition / Anthropic retrospectives (cyt. w RAH): coding często **mniej** parallelizable niż research — shared types → konflikt przy powrocie.

### Teza agent-first (MVP mill / empiria 2026)

- [../STRATEGY_AGENT_FIRST.md](../STRATEGY_AGENT_FIRST.md): najpierw **działająca** pętla ticket→PR→merge (nawet ~100% agentów), potem wycinanie slotów w deterministykę.
- Cursor: nie zaczęli od idealnego grafu — hill-climb od swarm → role → recursive ownership; **skrypt+JSON** pojawił się jako antidotum na drift, nie jako startowy UML.
- Copilot/Jules/Codex cloud, godark, Ouroboros: start od agent session → PR; CI/merge policy jako twardniejąca skorupa.
- Mazur: nie „wyrzuć graf”; graf/harness musi **zachować autonomię** (homeostat). Agent-first MVP = najpierw żywy autonom, potem organy w klocki.

### Jak czytać sprzeczność

```text
CEL DOJRZAŁY:     deterministyczny graf + LLM w wysokiej entropii
ŚCIEŻKA MVP:      agent w prawie każdym slocie → obserwuj → wycinaj
ANTYWZORZEC:     gruby graf bez dowozu issue→merge  LUB  continuous-executor z 10 kapeluszami
```

| Startujesz od… | Ryzyko | Mitigacja |
|----------------|--------|-----------|
| Idealnego grafu | Never-ship; stuck/ready limbo | Kryterium: N merged `ai/*` / okno czasu |
| 100% agentów na zawsze | Koszt, nondeterminism | Lista „kandydatów do wycinki” co tydzień |
| Flat swarm + lock file | Contention, unikanie ownership | Hierarchical ownership + handoff-only |
| Jednego „lead” agenta | Pathologie ról (Cursor #3) | Rozdziel plan vs code vs verify |

**ACE / RAH / Cursor orchestrate** schodzą się w hybrydzie: **deterministyczny szkielet orkiestracji** (script, DAG, delta merge) + **agentowe liście** z izolacją i handoffem — bez oddawania spine LLM-owi.

---

## 10. Szybka checklista implementacyjna (dla Lokaya / dark factory)

1. **Self-similar ownership:** ten sam protokół planner na każdym poziomie scope.
2. **Handoff-only workers:** zero peer chat; izolowana kopia; merge = task.
3. **Script holds the loop:** `plan.json` / `state.json` / events — agent nie jest durable runtime.
4. **Anti-fragile:** pad workera → respawn/split/escalate; nie global halt; świadomy error slack + green branch.
5. **Leaf verification:** bez taniego checka per subtask parent będzie racjonalizował garbage.
6. **Wycinaj stopniowo:** triage list, test command, merge policy → deterministyka; LLM zostaje przy wysokiej entropii.
7. **Self-improve z gate:** ACE playbook / Ouroboros core / DGM archive — nigdy silent self-mod production path.

---

## Indeks URL (płaski)

```
https://cursor.com/blog/self-driving-codebases
https://github.com/cursor/plugins/tree/main/orchestrate
https://cursor.com/blog/typescript-sdk
https://arxiv.org/abs/2606.13643
https://agentpatterns.ai/patterns/agent-design/recursive-agent-harnesses/
https://www.alexfeel.info/blog/dynamic-workflows-when-the-agent-writes-its-own-harness/
https://arxiv.org/abs/2512.24601
https://github.com/alexzhang13/rlm
https://arxiv.org/html/2608.08311
https://github.com/secondorderai/ouroboros
https://github.com/Q00/ouroboros
https://arxiv.org/abs/2510.04618
https://github.com/ace-agent/ace
https://ace-agent.github.io/
https://github.com/jennyzzt/dgm
https://arxiv.org/abs/2505.22954
https://github.com/Arvid-pku/Godel_Agent
https://arxiv.org/abs/2410.04444
https://github.com/minnesotanlp/meta-n
https://arxiv.org/html/2608.24735
https://github.com/eddieran/lindy-orchestrator
https://github.com/knot0-com/dagain
https://github.com/mrweixy/task-orchestrator
https://github.com/shbhmydv/Grindstone
https://github.com/thegpvc/gp-foundry
http://autonom.edu.pl
https://www.alphapebble.io/playbooks/dual-engine-architecture
https://winder.ai/ai-agent-harness-comparison/
```
