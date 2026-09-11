# INDEX — klepacz graph variants (50)

Wygenerowane 2026-09-11. **50** wariantów (fala 1 = 01–20; fala 2 = 21–50).
Dusza: [`../SOUL.md`](../SOUL.md) / workspace `_soul/SOUL.md`.

| # | Dir | Approach | Persona (skrót) | Subgraphs |
|---|-----|----------|-----------------|-----------|
| 01 | [`01-pragmatic-thin`](./01-pragmatic-thin/) | `from_scratch` | pragmatic minimalist — thinnest path that still ships ticket | 3 |
| 02 | [`02-optimistic-full`](./02-optimistic-full/) | `from_scratch` | optimistic — assume labels, CI, and humans cooperate; richer | 6 |
| 03 | [`03-pessimistic-gates`](./03-pessimistic-gates/) | `from_scratch` | pessimistic — fail-closed everywhere; assume flaky CI, dirty | 5 |
| 04 | [`04-cynical-cuts`](./04-cynical-cuts/) | `from_scratch` | cynical — delete half the nodes others invent; if a step doe | 3 |
| 05 | [`05-ready-for-agent-reuse`](./05-ready-for-agent-reuse/) | `reuse_ready` | reuse-ready maximal fidelity to berenddeboer/ready-for-agent | 4 |
| 06 | [`06-deerflow-borrow`](./06-deerflow-borrow/) | `compose_borrow` | deerflow-borrower compose — zapożycza pewniaczki ByteDance D | 5 |
| 07 | [`07-agentless-phases`](./07-agentless-phases/) | `compose` | agentless-deterministic — fixed localize→repair→validate; LL | 3 |
| 08 | [`08-fala-native`](./08-fala-native/) | `from_scratch` | fala-unix-atoms — many tiny Unix atoms ok/fail; pod-Fala for | 6 |
| 09 | [`09-label-fsm`](./09-label-fsm/) | `compose_label_fsm` | label-fsm-compose — stages as GitHub labels; GHA/scripts adv | 5 |
| 10 | [`10-human-amplify`](./10-human-amplify/) | `from_scratch` | human-amplify — human engineer + QA strategist at center; DE | 5 |
| 11 | [`11-planner-coder`](./11-planner-coder/) | `from_scratch` | dual-light-agents — plan-only SO + implement SO; optional ta | 6 |
| 12 | [`12-serial-k1`](./12-serial-k1/) | `from_scratch` | serial-strict — hard K=1: one ticket, one worktree, one PR;  | 4 |
| 13 | [`13-merge-policy`](./13-merge-policy/) | `reuse_ready` | merge-policy-first — reuse ready-for-agent Merge Policy Off/ | 4 |
| 14 | [`14-dot-pipeline`](./14-dot-pipeline/) | `compose` | dot-pipeline compose — blueprint.dot is the program; Pipelin | 4 |
| 15 | [`15-durable-steps`](./15-durable-steps/) | `compose` | durable-steps compose — Temporal/Inngest: DET Workflow + ste | 4 |
| 16 | [`16-guild-roles`](./16-guild-roles/) | `compose` | guild-roles compose — Dispatcher→Planner→Implementer→Reviewe | 4 |
| 17 | [`17-opa-merge-gate`](./17-opa-merge-gate/) | `from_scratch` | policy-as-code cynic — Rego/Conftest holds the merge button; | 3 |
| 18 | [`18-script-intake`](./18-script-intake/) | `from_scratch` | script-first pragmatic — intake = pure scripts (list → filte | 4 |
| 19 | [`19-bounded-repair`](./19-bounded-repair/) | `from_scratch` | bounded-escape pessimistic — hard N on repair_code and pr_re | 4 |
| 20 | [`20-from-zero`](./20-from-zero/) | `from_scratch` | blank-slate optimistic clarity — fresh stages from SOUL only | 6 |
| 21 | [`21-ralph-loop`](./21-ralph-loop/) | `compose` | ralph-wiggum-loop — continuous implement/review ticks until  | 4 |
| 22 | [`22-copilot-cloud`](./22-copilot-cloud/) | `reuse_ready` | copilot-cloud-reuse — issue→draft PR on ephemeral host; K=1; | 4 |
| 23 | [`23-claude-action`](./23-claude-action/) | `reuse_ready` | claude-action-reuse — maximal fidelity to anthropics/claude- | 4 |
| 24 | [`24-conductor-yaml`](./24-conductor-yaml/) | `compose` | conductor-yaml compose — Microsoft Conductor: YAML workflow  | 4 |
| 25 | [`25-jnurre-tdd`](./25-jnurre-tdd/) | `compose_jnurre_tdd` | jnurre-tdd-fsm compose — label-driven GHA FSM: triage → plan | 5 |
| 26 | [`26-holdout-oracle`](./26-holdout-oracle/) | `compose` | holdout-oracle compose — sealed holdout suite grades via exi | 4 |
| 27 | [`27-elasticclaw`](./27-elasticclaw/) | `compose` | elasticclaw-compose — ElasticClaw control plane: workflow YA | 4 |
| 28 | [`28-fabro-dot`](./28-fabro-dot/) | `compose` | fabro-dot compose — fabro.sh: Graphviz DOT workflow owns nex | 4 |
| 29 | [`29-codex-auto`](./29-codex-auto/) | `reuse_ready` | codex-auto-reuse — maximal fidelity to OpenAI Codex CLI in G | 4 |
| 30 | [`30-dagent-dag`](./30-dagent-dag/) | `compose` | dagent-dag compose — explicit TypeScript DAG watchdog; LLM o | 4 |
| 31 | [`31-inngest-steps`](./31-inngest-steps/) | `compose` | inngest-steps compose — Inngest event + createFunction; DET  | 4 |
| 32 | [`32-mastra-hybrid`](./32-mastra-hybrid/) | `hybrid` | mastra-hybrid — staged intake/triage/plan/review gates mixed | 4 |
| 33 | [`33-openfactory`](./33-openfactory/) | `compose` | openfactory compose — Temporal-ish state machine owns next s | 4 |
| 34 | [`34-jp-label-fix`](./34-jp-label-fix/) | `reuse_ready` | jp-label-reuse — maximal fidelity to JP DIY label auto-fix ( | 5 |
| 35 | [`35-phoenix-fsm`](./35-phoenix-fsm/) | `compose_phoenix_fsm` | phoenix-fsm compose — Watcher label SM Planner→Coder→Tester→ | 4 |
| 36 | [`36-knot-dag`](./36-knot-dag/) | `compose` | knot-dag compose — SQLite DAG executor owns plan/execute/ver | 4 |
| 37 | [`37-hue-action`](./37-hue-action/) | `reuse_ready` | hue-action-reuse — maximal fidelity to lennystepn-hue/issue2 | 4 |
| 38 | [`38-dryvist-gha`](./38-dryvist-gha/) | `compose` | dryvist-gha compose — reusable GHA workflow_call library: ai | 4 |
| 39 | [`39-luminik-pipeline`](./39-luminik-pipeline/) | `compose` | luminik-pipeline compose — fixed plan→approve→build→review→f | 4 |
| 40 | [`40-ableinc-fsm`](./40-ableinc-fsm/) | `compose_ableinc_fsm` | ableinc-fsm compose — fixed label FSM (agent-ready → agent-p | 4 |
| 41 | [`41-chippingway-fsm`](./41-chippingway-fsm/) | `compose_chippingway_fsm` | chippingway-fsm compose — workflow:* label + pinned JSON FSM | 5 |
| 42 | [`42-forge-stations`](./42-forge-stations/) | `compose` | forge-stations compose — LangGraph typed stations (plan/impl | 4 |
| 43 | [`43-klaus-dot`](./43-klaus-dot/) | `compose` | klaus-dot compose — klaus run on .dot; runtime fixed graph ( | 4 |
| 44 | [`44-wf-dsl`](./44-wf-dsl/) | `compose` | wf-dsl compose — artushin/conductor-ai: .wf DSL workflow eng | 4 |
| 45 | [`45-gha-native`](./45-gha-native/) | `compose` | gha-native compose — GitHub Actions is the program: issue_co | 5 |
| 46 | [`46-temporal-klepacz`](./46-temporal-klepacz/) | `compose` | temporal-klepacz compose — Temporal Workflow-as-code + Activ | 4 |
| 47 | [`47-prefect-flow`](./47-prefect-flow/) | `compose` | prefect-flow compose — Prefect @flow/@task DET spine; Deploy | 4 |
| 48 | [`48-dagster-assets`](./48-dagster-assets/) | `compose` | dagster-assets compose — Software-Defined Assets ticket→bran | 4 |
| 49 | [`49-windmill-flow`](./49-windmill-flow/) | `compose` | windmill-flow compose — Windmill scripts/flows as DET atoms; | 4 |
| 50 | [`50-cynical-min`](./50-cynical-min/) | `compose` | cynical-min compose — absolute DET spine pick→worktree→imple | 3 |

Total: **50** / 50
