# Process (binding)

**The product of Lokay is the process graph(s), not the workers.**
The **output** of that process is **quality code merged to `main`** — one
Definition of Done ([`WORKING.md`](WORKING.md)). A running graph that ships
nothing (or scrap) is not the product working.

Lokay’s valuable asset is one or more **Fala graphs** that describe how software
gets delivered: order, gates, retries, and close-out. Everything else is a
replaceable block under a stable contract.

## Hierarchy (non-negotiable)

1. **Fala graph(s)** — the process (what happens after what, what may fail closed,
   what may return into the queue).
2. **Unix atoms** — small processes with JSON envelopes; one job each.
3. **Adapters** — GitHub today, another host tomorrow; coding harness today,
   another `executor.command` tomorrow.

If the graph is right, you can swap firm A for firm B (language, framework,
tooling) and still get software delivered — provided the process is followed.
Lokay encodes that process so it can run continuously without reinventing it
every pass.

## Graphs are not one-way only

A single Fala path uses **conduction** (dependencies): a node is not ready until
upstream succeeded. That looks forward inside one path.

The **mill process as a whole is cyclic**:

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

## Atom contract (universal)

- One process = one job.
- JSON envelope on stdout (`ok` / `error` / job fields).
- No vendor knowledge inside Fala conduction.
- Deterministic or nondeterministic is a property of the **body**, not of the
  node id: the same graph slot may run a pure function today and an agent
  tomorrow if the envelope stays valid.
- Coding slot is only `run_agent` (config binary + args). No Pi/Claude/… hardcode
  in product paths. Swap = one small Unix script or config change.

## Agent / operator rules

When implementing in this repo:

1. Read the graph first (`fala/lokay.fala-package.toml`, `docs/GRAPH.md`).
2. Prefer a new or tighter **atom** over growing `compose/*`.
3. Prefer fixing a **block** over redesigning pass order.
4. Do not add human gates into the spine; residual human stays exceptional.
5. Do not invent a second process ledger next to Fala journals.
6. Do not treat the coding harness as the product.

## Related

- `docs/GRAPH.md` — path diagrams and conduction
- `docs/UNIX.md` — process boundaries and atom map
- `docs/WORKING.md` / `docs/AUTONOMY.md` — working mill contract
- `docs/NO_STUBS.md` — real executor only
- `AGENTS.md` — short agent-facing summary
