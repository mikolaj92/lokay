wave det-graph starting 2026-09-10T16:40Z

# Wave DET — finds log (deterministic spines)

**Data:** 2026-09-10 (PT / Europe/Warsaw)  
**Filtr:** orkiestracja = kod/graf durable; LLM tylko w jawnych slotach.  
**Karty:** `instances/<slug>/README.md` · tag `spine: deterministic`

---

## WAVE_DET_FIXED — karty napisane (7 NEW)

| Slug | ★ | Podejście | Confidence | Uwagi |
|------|---|-----------|------------|-------|
| [openautocoder-agentless](openautocoder-agentless/) | ~2109 | localize→repair→validate | **95** | Kanon Agentless; FSE’25 |
| [prnvh-plancompiler](prnvh-plancompiler/) | ~6 | PlanCompiler (1 LLM call) | **94** | Registry→7 checks→compile |
| [open-policy-agent-conftest](open-policy-agent-conftest/) | ~3259 | OPA/Conftest merge gates | **93** | Rego exit-code; 0 LLM w bramce |
| [microsoft-conductor](microsoft-conductor/) | ~427 | YAML+Jinja routes | **92** | MS Conductor ≠ artushin |
| [dubsopenhub-dark-factory](dubsopenhub-dark-factory/) | ~25 | sealed + scripted PR | **88** | Shadow Score Spec L4 |
| [thecraighewitt-agent-pipeline](thecraighewitt-agent-pipeline/) | ~1 | pure GHA issue→PR | **86** | 4 workflows; 1 agent slot |
| [brevity1swos-holdout](brevity1swos-holdout/) | ~0 | sealed/differential oracle | **84** | Exit-code grader; anti false-green |

### Odrzucone / odłożone (FIXED)

| Kandydat | Powód |
|----------|-------|
| **thegpvc/gp-foundry** | Już karta `thegpvc-gp-foundry` |
| **a7t-ai/three-body-agent** | Już `a7t-ai-three-body-agent` |
| **artushin/conductor-ai** | Już `artushin-conductor-ai` (inny produkt niż MS Conductor) |
| **temporal-community/temporal-ai-agent** / **temporal-agent-harness** | Durable hybrid → **WAVE_DET_TEMPORAL** |
| **mateaix/openagentsecurity** | API 404; wzmianka w karcie Conftest |
| **DUBSOpenHub/shadow-score-spec** | Spec alone — w `dubsopenhub-dark-factory` |

---

## WAVE_DET_TEMPORAL

**Focus:** Temporal, Cadence, Conductor (MS), Prefect, Windmill, Inngest, Trigger.dev + plain Python/Go FSM jako **deterministyczny spine** issue→PR.

**Skip:** `artushin-conductor-ai`, `darkshade9-prismconductor`; `microsoft-conductor` (już WAVE_DET_FIXED); `cursor-cloud-agents` (produkt na Temporal — spine w `temporal-workflow-spine`).

### Karty napisane (7 NEW)

| Slug | Confidence | Spine | LLM vs code (skrót) |
|------|------------|-------|---------------------|
| [temporal-workflow-spine](temporal-workflow-spine/) | 94 | Temporal Workflow + Activities | WF=CODE; implement/fix=LLM Activity; merge=CODE/signal |
| [plain-python-go-fsm](plain-python-go-fsm/) | 88 | Enum + transition table | transitions=CODE; agent functions=LLM activities |
| [prefect-pydantic-spine](prefect-pydantic-spine/) | 86 | Prefect `@flow`/`@task` + PrefectDurability | flow/HITL/tests=CODE; Agent.run=LLM tasks |
| [inngest-step-functions](inngest-step-functions/) | 84 | Event + `step.run` / `waitForEvent` | control=CODE; one step=LLM agent |
| [trigger-dev-tasks](trigger-dev-tasks/) | 83 | Trigger.dev v4 checkpoint tasks | task graph=CODE; agent turn=LLM inside |
| [uber-cadence-spine](uber-cadence-spine/) | 82 | Cadence WF/Activity (proto-Temporal) | identyczny kontrakt co Temporal |
| [windmill-flow-spine](windmill-flow-spine/) | 80 | Windmill flow + AI Agent step | edges/scripts/approval=CODE; AI step=LLM |

### Odrzucone / notatki (TEMPORAL)

| Kandydat | Powód |
|----------|--------|
| **microsoft/conductor** | Już skartowane w WAVE_DET_FIXED — nie duplikować |
| Netflix Conductor | Inny produkt; poza briefem AI ticket→PR |
| Restate / Hatchet | Poza listą nazw z briefu |
| Duplikat Cursor Temporal | Zostaje w `cursor-cloud-agents`; kontrakt w `temporal-workflow-spine` |

### Preferencje jakości (klepacz)

1. **Temporal** / **plain FSM** — najczystszy kontrakt „graph is code, agent is leaf”.  
2. **Prefect** / **Inngest** / **Trigger.dev** — szybki DX; merge/routing poza LLM step.  
3. **Windmill** — mocny gdy skrypty-tools już w platformie; unikaj chat-mode jako kolejki PR.  
4. **Cadence** — legacy/HA; greenfield → Temporal.  
5. **MS Conductor** — patrz FIXED (YAML+Jinja, 0 tokenów routingu).

### Metoda

WAVE3_DETERMINISTIC + PATTERNS P2.1 + WebSearch (Temporal harness, Prefect×Pydantic, Windmill AI agents, Inngest/Trigger 2026 comparisons). Karty PL: `spine:deterministic`, mermaid, tabela LLM vs code, Confidence, linki.

## WAVE_DET_DOT — 2026-09-10 (UTC+2 ~18:40–19:00)

Focus: klepacz issue→PR where ORCHESTRATION = deterministic code (compiled graph / GHA DAG / DOT→workflows / pure scripts); LLM only fills slots.

### Already skipped (under instances/)
- `thegpvc-gp-foundry` (harness.dot → GHA) — kanoniczny DOT→Actions; nie duplikować
- `fabro-sh-fabro`, `knot0-com-dagain`, `vsavkin-polygraph-factory`, pozostałe fale A–H

### NEW instances written (12)

| Slug | Repo | spine | Conf | Notes |
|------|------|-------|------|-------|
| samueljklee-attractor | samueljklee/attractor | DOT runner Py | 92 | Best RUN Attractor + software_factory.dot |
| point-labs-dev-arc | point-labs-dev/arc | DOT convergence | 90 | SPEC→verify; engine walks graph |
| jhugman-attractor-pi-dev | jhugman/attractor-pi-dev | DOT + pi.dev | 88 | npm CLI; Ralph issue loop DOT |
| campallison-attractor | campallison/attractor | DOT Go | 86 | 3-layer nlspec RUN |
| tgoodwin-tractor | tgoodwin/tractor | DOT binary | 84 | tractor reap; parallel audit |
| az9713-attractor-software-factory | az9713/attractor-software-factory | DOT + your_engine.py | 83 | 5+ blueprints; GUIDE.md stale |
| jmccarthy-attractor-c | jmccarthy/attractor-c | DOT C11 | 82 | ./attractor pipeline.dot |
| arikwaisman-klaus | arikWaisman/klaus | DOT TS | 81 | plan-and-execute.dot |
| luminik-io-alfred | luminik-io/alfred | fixed stages + merge_gate.py | 80 | nie DOT; merge policy = code |
| jawhnycooke-attractor | jawhnycooke/attractor | DOT Py | 80 | codergen leaf |
| jeffma8888-agent-foundry | jeffma8888/agent-foundry | foundry.config + dispatcher | 78 | hit na foundry.config search |
| harryaskham-caravan | harryaskham/caravan | merge queue DAG Rust | 76 | agent = repair leaf only |

### Honest REJECTED / not NEW card

| Query / candidate | Verdict |
|-------------------|---------|
| **gp-foundry forks** | **0 forks** na thegpvc/gp-foundry; brak klonów konsumenckich z własnym harness.dot |
| **harness.dot** | praktycznie unikalne dla thegpvc/gp-foundry (reszta: mic_harness.dot audio / .dotx viewer — nie factory) |
| **foundry.config.yaml** | tylko ekosystem gp-foundry; Palantir `foundry.config.json` = OSDK hosting, nie agent mill |
| **GENERATED FROM harness.dot** | wyłącznie thegpvc/gp-foundry |
| strongdm/attractor | **specs only** (nlspec) — nie RUN |
| brynary/attractor | archived → „use fabro”; fabro już w KB |
| martinemde/attractor | fork specs „Claude is creating Go impl” — nie kompletny runner jako produkt |
| wcraigjones/attractor-factory | specs / attractor-spec.md only |
| amolstrongdm/attractor | scenarios/DTU factory; nie DOT-as-spine primary |
| entropy-cloud/attractor-guided-engineering-template | metafora AGE + docs; nie DOT issue→PR mill |
| wolverin0/clawtrol | merge_gate bin istnieje, ale orkiestracja = kanban/UI fleet — nie compiled fixed graph |
| wielas/forge | L4 Hermes kanban; merge_gate w scripts — nie DOT→workflows |
| 11suixing11/github-maintainer-agent | merge_gate w Python controller — blisko, ale single-agent paced maintainer; opcjonalnie później |
| Alezrik/attractor-phoenix, jaytaylor/attractor-php, nnunley/strange-lettractor | RUN Attractor w innych językach — świadomie odłożone (limit fali; wzorzec pokryty) |

### Search coverage
gh: harness.dot, foundry.config, merge_gate, gp-foundry, attractor software factory, digraph+prompt DOT, GENERATED FROM harness, forks API.
