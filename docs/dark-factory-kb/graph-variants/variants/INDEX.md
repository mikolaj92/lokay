# INDEX — klepacz graph variants (fala 1)

Wygenerowane 2026-09-11. **20** niezależnych wersji (graf + podgrafy).
Dusza: [`../SOUL.md`](../SOUL.md) / workspace `_soul/SOUL.md`.

Cel: porównać i **składać** fragmenty — nie wybrać jednego monolitu.

| # | slug | approach | persona | subgraphs |
|---|------|----------|---------|-----------|
| 01 | [`01-pragmatic-thin`](./01-pragmatic-thin/) | `from_scratch` | pragmatic minimalist — thinnest path that still ships ticket | 3: implement, intake, review-merge |
| 02 | [`02-optimistic-full`](./02-optimistic-full/) | `from_scratch` | optimistic — assume labels, CI, and humans cooperate; richer | 6: ci-trust, implement-ship, label-intake, plan-enrich, post-merge, review-merge |
| 03 | [`03-pessimistic-gates`](./03-pessimistic-gates/) | `from_scratch` | pessimistic — fail-closed everywhere; assume flaky CI, dirty | 5: ci-babysit, failure-escape, preflight, review-merge, ship |
| 04 | [`04-cynical-cuts`](./04-cynical-cuts/) | `from_scratch` | cynical — delete half the nodes others invent; if a step doe | 3: code-to-pr, gate, pick |
| 05 | [`05-ready-for-agent-reuse`](./05-ready-for-agent-reuse/) | `reuse_ready` | reuse-ready maximal fidelity to berenddeboer/ready-for-agent | 4: agent-leaf, label-start, merge-policy, worktree |
| 06 | [`06-deerflow-borrow`](./06-deerflow-borrow/) | `compose_borrow` | deerflow-borrower compose — zapożycza pewniaczki ByteDance D | 5: agent-leaf-gh, busy-buffer, merge-policy-det, uuid5-threads, webhook-ff |
| 07 | [`07-agentless-phases`](./07-agentless-phases/) | `compose` | agentless-deterministic — fixed localize→repair→validate; LL | 3: localize, repair, validate |
| 08 | [`08-fala-native`](./08-fala-native/) | `from_scratch` | fala-unix-atoms — many tiny Unix atoms ok/fail; pod-Fala for | 6: implement-test, pick, plan-so, pr, review-merge, worktree |
| 09 | [`09-label-fsm`](./09-label-fsm/) | `compose_label_fsm` | label-fsm-compose — stages as GitHub labels; GHA/scripts adv | 5: implement-validate, label-spine, merge-escape, review-fix, triage-plan |
| 10 | [`10-human-amplify`](./10-human-amplify/) | `from_scratch` | human-amplify — human engineer + QA strategist at center; DE | 5: arch-gate, babysit, qa-audit, review-merge, ship |
| 11 | [`11-planner-coder`](./11-planner-coder/) | `from_scratch` | dual-light-agents — plan-only SO + implement SO; optional ta | 6: git-pr, implement, intake, plan, review-merge, task-breakdown |
| 12 | [`12-serial-k1`](./12-serial-k1/) | `from_scratch` | serial-strict — hard K=1: one ticket, one worktree, one PR;  | 4: claim-k1, implement-one-pr, occupancy-det, review-merge |
| 13 | [`13-merge-policy`](./13-merge-policy/) | `reuse_ready` | merge-policy-first — reuse ready-for-agent Merge Policy Off/ | 4: classify-so, coder-ceiling, policy-star, verdict-exec |
| 14 | [`14-dot-pipeline`](./14-dot-pipeline/) | `compose` | dot-pipeline compose — blueprint.dot is the program; Pipelin | 4: blueprint, box-llm, det-walk, hitl-exit |
| 15 | [`15-durable-steps`](./15-durable-steps/) | `compose` | durable-steps compose — Temporal/Inngest: DET Workflow + ste | 4: det-steps, hitl-wait, llm-activity, workflow-spine |
| 16 | [`16-guild-roles`](./16-guild-roles/) | `compose` | guild-roles compose — Dispatcher→Planner→Implementer→Reviewe | 4: dispatch, implementer, planner, reviewer |
| 17 | [`17-opa-merge-gate`](./17-opa-merge-gate/) | `from_scratch` | policy-as-code cynic — Rego/Conftest holds the merge button; | 3: opa-merge-gate, optional-review-so, ticket-to-pr |
| 18 | [`18-script-intake`](./18-script-intake/) | `from_scratch` | script-first pragmatic — intake = pure scripts (list → filte | 4: implement-ship, optional-plan, review-merge, script-intake |
| 19 | [`19-bounded-repair`](./19-bounded-repair/) | `from_scratch` | bounded-escape pessimistic — hard N on repair_code and pr_re | 4: intake, pr-repair, repair-code, skip-escape |
| 20 | [`20-from-zero`](./20-from-zero/) | `from_scratch` | blank-slate optimistic clarity — fresh stages from SOUL only | 6: critical-review, git-pr, implement, merge-human, pm-next, ticket |

## Approaches
- `compose`: 4
- `compose_borrow`: 1
- `compose_label_fsm`: 1
- `from_scratch`: 12
- `reuse_ready`: 2

