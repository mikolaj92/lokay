# Atom locality: graph, implementation, execution evidence

## Invariant

The unit of work in Fala must have a bounded implementation and an identifiable
execution record. Small wrappers around hidden workflows do not satisfy this.
Failure location is not necessarily root cause: follow validated inputs and
causation before choosing a repair target. Never blindly replay external effects.

## Sequence

1. Read-only structural inventory: authored path/effector/atom -> source sites.
   Report unresolved/template bindings explicitly. Do not invoke handlers to
   discover ownership. Source candidates are evidence, not proven dispatch.
   Separate repeated authored nodes from distinct atom implementations.
2. Explicit dispatch ownership and immutable implementation provenance in the
   existing Fala result/journal boundary. Pin actual execution code, not current
   checkout HEAD after a host update. Include upstream and attempt references;
   no secrets or automatic raw-input publication.
3. Move pre-pass harvesting into an authored Fala flow and split observation,
   classification, and persistence. Preserve cooldown, occupancy and recovery
   semantics. README state machine first, then graph, then implementations.
4. Contract-scoped failure inspection and regression verification. A report must
   distinguish failed contract, upstream defect, shared dependency and unknown
   cause. Safe local tests are not automatic retries of live effects.
5. Apply the inventory to remaining atom families. Each confirmed hidden flow
   gets its own bounded migration ticket; do not mechanically split every helper
   into a process or use LOC as a correctness verdict.

## Acceptance

- Graph and packaged copy remain synchronized after every routing change.
- Each migrated boundary has positive, negative and recovery tests.
- Unresolved mappings remain visible; no invented precision from Ripwire edges.
- Read-only tools cannot run adapters or write product journals.
- Ripwire supplements source evidence; it is optional, never dispatch authority.
- Completion means verified changes on main, not this plan or opened tickets.

## First slice

Ship a read-only JSON inventory over the authored manifest and Python source.
This is deliberately not expanded-runtime graph identity and not proof of atom
locality. It exposes exact source locations for review and missing mappings.
Further steps replace candidates with authoritative bindings and execution data.
