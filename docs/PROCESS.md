# Process (binding)

**The product of Lokay is the process graph(s), not the workers. The graph is
the accumulated value.**

The graph preserves the knowledge of how software gets delivered: order,
state, gates, retries, return edges, side-effect authority, and close-out.
Everything built around it is a replaceable implementation of one node under a
stable contract. A node may be executed by a small Unix program, deterministic
function, agent, human, or service. Its nature does not determine its place in
the process.

```text
node = role + contract + capabilities
executor = replaceable implementation of the node
product = graph + state + transition rules + Definition of Done
```

The **output** of that process is **quality code merged to `main`** — one
Definition of Done ([`WORKING.md`](WORKING.md)). A running graph that ships
nothing (or scrap) is not the product working. Likewise, a stronger model only
improves a block; a better graph improves every present and future executor.
Never hide accumulated process knowledge in a worker prompt, Python composer,
UI, or vendor harness.

## Hierarchy (non-negotiable)

1. **Fala graph(s)** — the process (what happens after what, what may fail closed,
   what may return into the queue).
2. **Unix atoms** — the universal node boundary: one small process, one job,
   one JSON envelope. Its body may use deterministic code, an agent, a human,
   or a service; Fala does not privilege one kind of executor.
3. **Adapters** — GitHub today, another host tomorrow; coding harness today,
   another `executor.command` tomorrow.

If the graph is right, you can swap firm A for firm B (language, framework,
tooling) and still get software delivered — provided the process is followed.
Lokay encodes that process so it can run continuously without reinventing it
every pass. In Lokay, even an agent, human handoff, or remote service enters the
graph through the same small Unix-process contract. The implementation may be
non-deterministic; the composition remains explicit.

## Graphs are not one-way only

A single Fala path uses **conduction** (dependencies): a node is not ready until
upstream succeeded. That looks forward inside one path.

The **lokay process as a whole is cyclic**:

- red suite → bounded repair → recheck
- conflicting PR → close → re-ready → later `issue_to_pr`
- failed implement → stuck / blocked → next seed
- continuous `factory_pass` ticks re-survey and re-enter work
- event wake re-enters triage / close-out

So: local path order is structured; fleet behavior allows return, repeat, and
retry across passes. Do not flatten the product into a single irreversible DAG
of “issue → done”.

## What to change vs what to protect

| Change freely (blocks) | Change rarely (process) |
| --- | --- |
| Atom body (`src/lokay/proc/…`) | Authored paths in `fala/lokay.fala-package.toml` |
| `executor.command` / `args` (any real harness) | Conduction / fail-closed gates between stages |
| GitHub CLI details behind list/label/PR atoms | Per-repo PR-first, serial implement budget, residual human |
| Local test command, worktree layout | Health meanings (idle / waiting / stall / …) |

**Default work:** improve a small block while keeping the graph’s meaning.
**Exceptional work:** edit the graph — only when the *process* itself must change,
and document why in `docs/GRAPH.md` / this file.

## Entropy: reduce uncertainty, then conduct effects

An agent **minimizes entropy**: uncertain evidence becomes a validated,
closed-schema decision or scoped code artifact. Known hard facts terminate
before inference. Fala owns validation, bounded retry/evidence requests,
publication, labels, lists, gates and merge. No agent substitutes for listing,
`host_ff`, merging or `resolve_issue_hard_facts`.

Issue triage has one decision boundary: hard facts → agent only if needed →
validation/evidence → publish. `issue_sieve_row` consumes that decision; words
such as superseded, duplicate or shape do not trigger a second intake engine
(#1031). `intake_check_execution` remains an explicit named-check CLI/dispatch
capability, not a competing READY/CLOSE after triage. Shape and named-path
evidence belong inside the existing triage evidence branch (#1001). Published
verdicts are park / ready / close / skip / split only — zero `needs_human`.

Parent department *bodies* start high-entropy (`departments.agent_bodies`,
default on). The five `run_*_department` slots keep their authored child Falas
and envelopes; the agent must describe inner steps in `trace` and may return
`route=child` to run the authored child. Deterministic atoms replace pieces
later, one contract at a time. The graph geometry does not change.

The allowlist names actual organ bindings, not suffixes or vendor harnesses.
Code workers return a transport envelope and scoped worktree changes; those
still require real diff, local verification and publication gates.

| Binding | Class | Uncertainty → bounded result |
| --- | --- | --- |
| `run_self_repair_department` | entropy (body) | Stall facts → department envelope; authored child is fallback |
| `run_issue_triage_department` | entropy (body) | Open issues → sieve envelope; authored child is fallback |
| `run_executor_department` | entropy (body) | Do-row → open PR occupancy; authored child is fallback |
| `run_pr_triage_department` | entropy (body) | Open PRs → merge/feedback/repair verdict; authored child is fallback |
| `run_pr_repair_department` | entropy (body) | Repair verdict → repaired branch; authored child is fallback |
| `issue_triage_agent` | entropy | Issue and hard facts → triage decision |
| `issue_triage_retry_agent` | entropy | Invalid triage and feedback → corrected decision |
| `issue_evidence_agent` | entropy | Requested evidence → triage decision |
| `run_localization_agent` | entropy | Optional / off happy path (#1032). Issue and tree → edit-path proposal |
| `retry_localization_agent` | entropy | Rejected paths → corrected proposal |
| `run_relocalization_agent` | entropy | Existing diff and scope → scope reconciliation |
| `retry_relocalization_agent` | entropy | Reconciliation feedback → corrected proposal |
| `queue_conflict_agent` | entropy | Unresolved overlap → reconciliation decision |
| `queue_conflict_retry_agent` | entropy | Invalid reconciliation → corrected decision |
| `run_agent` | entropy | Localized issue or PR repair → scoped code changes |
| `coding_retry_agent` | entropy | Coding feedback → corrected changes |
| `local_repair_retry_agent` | entropy | Invalid local repair result and validator feedback → corrected coding result |
| `evidence_coding_agent` | entropy | Requested coding evidence → scoped changes |
| `repair_agent` | entropy | Failed local tests → scoped repair |
| `pr_repair_retry_agent` | entropy | Failed repair contract → corrected changes |
| `evidence_repair_agent` | entropy | Requested repair evidence → scoped changes |
| `pr_test_repair_agent` | entropy | PR test failure → scoped repair |
| `pr_review_agent` | entropy | Exact SHA and evidence → review verdict |
| `pr_review_retry_agent` | entropy | Invalid review → corrected verdict |
| `evidence_review_agent` | entropy | SHA-bound evidence → review verdict |
| `self_repair_run_agent` | entropy | Factory incident and scope → candidate code repair |

Campaign: bounded authoring #996, retired surfaces #998, removed Python survey
chain #999, semantic contracts #1000, single triage boundary #1001. Fala remains
the process, not a worker prompt or a Python sequence.

## Atom contract (universal)

- One process = one job.
- JSON envelope on stdout (`ok` / `error` / job fields).
- No vendor knowledge inside Fala conduction.
- Deterministic or nondeterministic, machine or human, is a property of the
  **body**, not of the node id: the same graph slot may run a Unix program,
  pure function, agent, human, or service if the contract stays valid.
- Coding slot is only `run_agent` (config binary + args). No Pi/Claude/… hardcode
  in product paths. Swap = one small Unix script or config change.

## Agent / operator rules

When implementing in this repo:

1. Read the graph first (`fala/lokay.fala-package.toml`, `docs/GRAPH.md`).
2. Prefer a new or tighter **atom** over growing `compose/*`.
3. Prefer fixing a **block** over redesigning pass order.
4. Do not add human gates into the spine; residual human stays exceptional.
   Foreign objections to what Lokay *is* CLOSE. Hangs / does-not-work-as-described stay.
5. Do not invent a second process ledger next to Fala journals.
6. Do not treat the coding harness as the product.

## Related

- `docs/GRAPH.md` — path diagrams and conduction
- `docs/DARK_FACTORY_ARCHETYPE.md` — non-binding synthesis of the shared geometry across deterministic-first software factories
- `docs/UNIX.md` — process boundaries and atom map
- `docs/WORKING.md` / `docs/AUTONOMY.md` — working lokay contract
- `docs/NO_STUBS.md` — real executor only
- `AGENTS.md` — short agent-facing summary
