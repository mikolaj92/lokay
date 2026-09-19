# Porównanie 50 wariantów klepacza vs cienki WORKING spine

Data: **2026-09-11**. Baseline: `dark-factory-kb/WORKING_KLEPACZ_GRAPH.md` + `KLEPACZ.md`.
Rubryka 8×0–5 (max **40**): `soul_fit` · `det_spine` · `thinness` · `label_start` · `coder_ceiling` · `bounded_repair` · `so_leaves` · `implementability`.
Tagi: `keep` (prawie drop-in) · `borrow` (1–3 wzorce) · `inspire` (ciężkie/egzotyczne) · `skip` (konflikt z SOUL / entropia).

## Cienki vs gruby dziś

Cienki kanon WORKING to stały łańcuch **host_ff → pick_one_labeled → occupancy → worktree → plan SO → implement SO → run_tests → (repair_code max N) → open_pr → pr_review SO → (pr_repair max N) → MergePolicy Off|Classify|Always**: agent **nie routuje**, LLM siedzi tylko w liściach ze structured output, a człowiek trzyma architekturę i (domyślnie) merge. Obecny `factory_pass` jest przeciwieństwem — pięć departmentów plus recovery, harvest, stuck, leftover, pass_ceiling i chmara `select_*`: topologia „niby OK”, ale entropia weszła w orkiestrację (survey/ready/limbo), więc Lokaj nie dowozi ticket→PR. Wariant wygrywa, gdy jest bliżej 6–12 atomów niż 40, startuje od etykiety (nie czatu) i da się włożyć w Fala / issue #1138–#1141 bez Temporal/Dagster/Windmill.

## Top 10

| # | slug | total | tag | dlaczego |
|---|------|------:|-----|----------|
| 01 | `pragmatic-thin` | **39** | `keep` | Prawie 1:1 z WORKING: cienki FSM label→PR→policy, SO-liście, bez tłuszczu. |
| 19 | `bounded-repair` | **38** | `keep` | Hard N na repair_code i pr_repair; po wyczerpaniu skip+receipt, zero limbo stamps. |
| 08 | `fala-native` | **37** | `keep` | Natywne Fala ok|fail atomy + pod-Fala — mapuje wprost na lokay #1138–#1141. |
| 12 | `serial-k1` | **36** | `keep` | Twarde K=1 occupancy DET: jeden ticket, jeden worktree, jeden PR — bez siewu katalogu. |
| 04 | `cynical-cuts` | **35** | `keep` | Cyniczne cięcia: jeśli węzeł nie przesuwa PR — wywal; blisko cienkiego spine. |
| 05 | `ready-for-agent-reuse` | **35** | `keep` | Maksymalna wierność ready-for-agent: label start + MergePolicy Off|Classify|Always. |
| 13 | `merge-policy` | **35** | `keep` | MergePolicy jako gwiazda: coder nigdy nie merguje; Classify SO tylko gdy gałka=Classify. |
| 18 | `script-intake` | **35** | `keep` | Intake 100% skryptami list→filter→pick; zero LLM przed pick — kanon pick_one_labeled. |
| 09 | `label-fsm` | **34** | `borrow` | Label-FSM (workflow:*): GHA/skrypt flipuje etykiety; agent nigdy nie routuje — za dużo stanów na start. |
| 11 | `planner-coder` | **34** | `keep` | Dual light agents plan+implement SO; git/PR zawsze DET — rdzeń WORKING. |

## Bottom 5 / skip

| # | slug | total | tag | dlaczego |
|---|------|------:|-----|----------|
| 20 | `from-zero` | **23** | `skip` | Blank-slate z pm/next_job — pachnie chat-pickiem i PM-orkiestracją, nie label impulse. |
| 32 | `mastra-hybrid` | **20** | `skip` | Mastra hybrid free-sandbox build = agent dostaje luz w stacji — konflikt z det_spine/SOUL. |
| 16 | `guild-roles` | **24** | `inspire` | Guild Dispatcher→Planner→Implementer→Reviewer — ładne role, za dużo orkiestracji. |
| 49 | `windmill-flow` | **26** | `inspire` | Windmill flows/scripts — DET atoms w obcym SaaS; niska implementability. |
| 24 | `conductor-yaml` | **27** | `inspire` | MS Conductor YAML+Jinja 0-token orchestration — piękny DET, zero mapowania na Fala dziś. |

Dodatkowo `skip`: **20-from-zero** (pm/next_job ≈ chat-pick) oraz **32-mastra-hybrid** (free sandbox = agent routing). Rodzina Temporal/Prefect/Dagster/Windmill (46–49) ma wysoki `det_spine`, ale `implementability=1` — inspire, nie keep.

## Pattern borrow (co ukraść do WORKING)

- **Label = start; intake 100% DET (list→filter→pick, zero LLM przed pick)** ← 01, 05, 18, 23, 34, 38
- **Twarde K=1 occupancy / jeden worktree / zero siewu katalogu mid-flight** ← 12, 40, 05, 34
- **Coder ceiling = open/draft PR; MergePolicy Off|Classify|Always jako gałka DET** ← 13, 05, 50, 01, 22
- **Bounded repair max N + skip/receipt; zakaz limbo stamps (`ai:limbo` itd.)** ← 19, 03, 25, 34, 09
- **SO leaves only: plan / implement / review; git+test+PR = DET** ← 11, 08, 19, 40, 01
- **Fail-closed escape + DET policy na merge (OPA/predicate); LLM review tylko doradczy** ← 03, 17, 39, 13
- **Fala ok|fail atomy + pod-Fala na pętle repair (`when=`)** ← 08
- **Cut rule: węzeł bez postępu PR → delete (cyniczny minimalizm)** ← 04, 50
- **Ścieżka wybierana eventem/mode (issue|fix|rebase), nie LLM-routerem** ← 37, 09, 45
- **Reviewer ≠ implementer; humans own outcome / no self-merge** ← 16, 11, 25, 01
- **Circuit breaker: revision_cap / max_conflict_rounds / soft_max_ticks** ← 25, 41, 21, 30
- **Lease/mutex: SQLite lease lub one-active-stage label** ← 40, 09, 12

## Rekomendowane merge do WORKING_KLEPACZ_GRAPH (konkretne delty)

1. **Zostaw spine 01+08 jako kanon topologii** — te same węzły co WORKING; implementuj jako pakiet Fala (ok|fail), nie jako nowy silnik.
2. **Wklej kontrakty SO z 11/01** — `plan_issue` / `implement|repair_code|pr_repair` / `pr_review` JSON jak w WORKING (ok:false + enum reason → skip, nie limbo).
3. **Z 18: zrób `pick_one_labeled` czystym skryptem** — `gh issue list` → filter `ready-for-agent|ai:ready` → K=1; zakaz LLM i „find similar” gdy pusto.
4. **Z 12: occupancy DET przed worktree** — live launch → defer; dead wrapper bez PR → finish_orphan; free → worktree_add; zero catalog seed.
5. **Z 19: liczniki DET `repair_code_n` / `pr_repair_n`** — po N: `skip_receipt` + HITL ping; lista zakazanych limbo labels; nigdy nie otwieraj PR na lokalnym red.
6. **Z 13: MergePolicy Off default** — Classify SO tylko gdy gałka=Classify; Always tylko low-risk + zielone CI; nigdy LLM-merge.
7. **Z 04/50: cut list w docs** — wyłącz (nie kasuj historii): dual survey, stuck.json limbo, leftover/ready=0/pass_ceiling recovery, fat product_entry 8-slot, department-orchestrator tool loops.
8. **Z 17 (lekko): Classify/Always = reguły DET** — choćby prosty skrypt/rego-lite na risk+CI; `pr_review` SO tylko advisory przy Always.
9. **Nie bierz** Temporal/Inngest/Prefect/Dagster/Windmill/Conductor/DOT-fabro jako runtime — najwyżej ideę step-scoped retry / HITL wait.
10. **Self-repair zostaje XOR tylko na stall maszyny** (WORKING pewniaczek #9) — nie na leftover produktu.

## Keep shortlist (drop-in / near)

- `01-pragmatic-thin` (**39**) — Prawie 1:1 z WORKING: cienki FSM label→PR→policy, SO-liście, bez tłuszczu.
- `19-bounded-repair` (**38**) — Hard N na repair_code i pr_repair; po wyczerpaniu skip+receipt, zero limbo stamps.
- `08-fala-native` (**37**) — Natywne Fala ok|fail atomy + pod-Fala — mapuje wprost na lokay #1138–#1141.
- `12-serial-k1` (**36**) — Twarde K=1 occupancy DET: jeden ticket, jeden worktree, jeden PR — bez siewu katalogu.
- `04-cynical-cuts` (**35**) — Cyniczne cięcia: jeśli węzeł nie przesuwa PR — wywal; blisko cienkiego spine.
- `05-ready-for-agent-reuse` (**35**) — Maksymalna wierność ready-for-agent: label start + MergePolicy Off|Classify|Always.
- `13-merge-policy` (**35**) — MergePolicy jako gwiazda: coder nigdy nie merguje; Classify SO tylko gdy gałka=Classify.
- `18-script-intake` (**35**) — Intake 100% skryptami list→filter→pick; zero LLM przed pick — kanon pick_one_labeled.
- `11-planner-coder` (**34**) — Dual light agents plan+implement SO; git/PR zawsze DET — rdzeń WORKING.
- `50-cynical-min` (**34**) — Absolutne min: pick→worktree→implement→test→draft PR→human; MergePolicy Off only.

## Pełna tabela (50)

| # | slug | total | tag | soul | det | thin | label | ceil | repair | so | impl |
|---|------|------:|-----|-----:|----:|-----:|------:|-----:|-------:|---:|-----:|
| 01 | `pragmatic-thin` | **39** | `keep` | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 |
| 02 | `optimistic-full` | **31** | `borrow` | 5 | 4 | 2 | 5 | 5 | 3 | 4 | 3 |
| 03 | `pessimistic-gates` | **33** | `borrow` | 5 | 5 | 2 | 5 | 5 | 4 | 4 | 3 |
| 04 | `cynical-cuts` | **35** | `keep` | 5 | 5 | 5 | 5 | 5 | 2 | 3 | 5 |
| 05 | `ready-for-agent-reuse` | **35** | `keep` | 5 | 5 | 4 | 5 | 5 | 3 | 4 | 4 |
| 06 | `deerflow-borrow` | **28** | `inspire` | 4 | 4 | 2 | 4 | 5 | 3 | 4 | 2 |
| 07 | `agentless-phases` | **32** | `borrow` | 4 | 5 | 3 | 4 | 5 | 4 | 4 | 3 |
| 08 | `fala-native` | **37** | `keep` | 5 | 5 | 3 | 5 | 5 | 4 | 5 | 5 |
| 09 | `label-fsm` | **34** | `borrow` | 5 | 5 | 2 | 5 | 5 | 4 | 4 | 4 |
| 10 | `human-amplify` | **30** | `borrow` | 5 | 4 | 2 | 4 | 5 | 3 | 4 | 3 |
| 11 | `planner-coder` | **34** | `keep` | 5 | 4 | 3 | 4 | 5 | 3 | 5 | 5 |
| 12 | `serial-k1` | **36** | `keep` | 5 | 5 | 4 | 5 | 5 | 3 | 4 | 5 |
| 13 | `merge-policy` | **35** | `keep` | 5 | 5 | 4 | 5 | 5 | 2 | 4 | 5 |
| 14 | `dot-pipeline` | **29** | `inspire` | 4 | 5 | 3 | 3 | 5 | 3 | 4 | 2 |
| 15 | `durable-steps` | **28** | `inspire` | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 1 |
| 16 | `guild-roles` | **24** | `inspire` | 4 | 3 | 2 | 3 | 5 | 2 | 3 | 2 |
| 17 | `opa-merge-gate` | **30** | `borrow` | 4 | 5 | 3 | 5 | 5 | 2 | 3 | 3 |
| 18 | `script-intake` | **35** | `keep` | 5 | 5 | 4 | 5 | 5 | 2 | 4 | 5 |
| 19 | `bounded-repair` | **38** | `keep` | 5 | 5 | 3 | 5 | 5 | 5 | 5 | 5 |
| 20 | `from-zero` | **23** | `skip` | 4 | 3 | 2 | 2 | 4 | 2 | 3 | 3 |
| 21 | `ralph-loop` | **29** | `inspire` | 4 | 3 | 2 | 4 | 5 | 4 | 4 | 3 |
| 22 | `copilot-cloud` | **29** | `borrow` | 5 | 4 | 4 | 4 | 5 | 2 | 3 | 2 |
| 23 | `claude-action` | **32** | `borrow` | 5 | 5 | 4 | 5 | 5 | 2 | 3 | 3 |
| 24 | `conductor-yaml` | **27** | `inspire` | 4 | 5 | 2 | 3 | 5 | 3 | 4 | 1 |
| 25 | `jnurre-tdd` | **33** | `borrow` | 5 | 5 | 2 | 5 | 5 | 4 | 4 | 3 |
| 26 | `holdout-oracle` | **28** | `inspire` | 4 | 5 | 3 | 4 | 5 | 2 | 3 | 2 |
| 27 | `elasticclaw` | **27** | `inspire` | 4 | 5 | 2 | 3 | 5 | 3 | 4 | 1 |
| 28 | `fabro-dot` | **29** | `inspire` | 4 | 5 | 3 | 3 | 5 | 3 | 4 | 2 |
| 29 | `codex-auto` | **32** | `borrow` | 5 | 5 | 4 | 5 | 5 | 2 | 3 | 3 |
| 30 | `dagent-dag` | **29** | `inspire` | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 2 |
| 31 | `inngest-steps` | **29** | `inspire` | 4 | 5 | 2 | 4 | 5 | 4 | 4 | 1 |
| 32 | `mastra-hybrid` | **20** | `skip` | 3 | 2 | 2 | 3 | 4 | 2 | 2 | 2 |
| 33 | `openfactory` | **27** | `inspire` | 4 | 5 | 2 | 3 | 5 | 3 | 4 | 1 |
| 34 | `jp-label-fix` | **34** | `borrow` | 5 | 5 | 3 | 5 | 5 | 4 | 3 | 4 |
| 35 | `phoenix-fsm` | **29** | `inspire` | 4 | 4 | 2 | 5 | 5 | 4 | 3 | 2 |
| 36 | `knot-dag` | **27** | `inspire` | 4 | 5 | 2 | 3 | 5 | 3 | 3 | 2 |
| 37 | `hue-action` | **32** | `borrow` | 5 | 5 | 3 | 5 | 5 | 3 | 3 | 3 |
| 38 | `dryvist-gha` | **31** | `borrow` | 5 | 5 | 3 | 5 | 5 | 2 | 3 | 3 |
| 39 | `luminik-pipeline` | **29** | `inspire` | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 2 |
| 40 | `ableinc-fsm` | **34** | `borrow` | 5 | 5 | 3 | 5 | 5 | 2 | 5 | 4 |
| 41 | `chippingway-fsm` | **28** | `inspire` | 4 | 5 | 1 | 4 | 5 | 4 | 3 | 2 |
| 42 | `forge-stations` | **28** | `inspire` | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 1 |
| 43 | `klaus-dot` | **30** | `inspire` | 4 | 5 | 2 | 4 | 5 | 4 | 4 | 2 |
| 44 | `wf-dsl` | **27** | `inspire` | 4 | 5 | 2 | 3 | 5 | 3 | 4 | 1 |
| 45 | `gha-native` | **30** | `borrow` | 5 | 5 | 3 | 3 | 5 | 2 | 4 | 3 |
| 46 | `temporal-klepacz` | **28** | `inspire` | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 1 |
| 47 | `prefect-flow` | **28** | `inspire` | 4 | 5 | 2 | 4 | 5 | 3 | 4 | 1 |
| 48 | `dagster-assets` | **29** | `inspire` | 4 | 5 | 2 | 5 | 5 | 3 | 4 | 1 |
| 49 | `windmill-flow` | **26** | `inspire` | 4 | 5 | 2 | 3 | 5 | 2 | 4 | 1 |
| 50 | `cynical-min` | **34** | `keep` | 5 | 5 | 5 | 5 | 5 | 1 | 3 | 5 |

---

**Rekomendacja końcowa:** wdrażaj WORKING jako `01-pragmatic-thin` + atomy `08-fala-native`, doklejając z `19` bounded repair, z `18/12` DET pick+K=1 i z `13` MergePolicy Off — resztę 50 traktuj jako katalog pożyczek, nie nowy „mill” — tylko Lokaj.
