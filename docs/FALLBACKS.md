# Super-fallback inventory (issue #19)

Rarely executed compat / legacy / shim paths. **Rule:** delete zombies, or promote
to explicit first-class features with tests — never leave silent dual paths for
AI to reintroduce.

Related: issue #17 (graph_run placeholders), issue #18 (AI agent fail-closed),
[`NO_STUBS.md`](NO_STUBS.md).

## Inventory and decisions

| Symbol / path | Kind | Decision | Notes |
| --- | --- | --- | --- |
| `lokay.grok_agent` re-export | compat shim | **Deleted** | Prefer `lokay.agent`; zero importers |
| `gh_prs.pr_checks_green` | compat wrapper | **Deleted** | Superseded by `pr_checks_report`; zero callers |
| `graph_run` hardcode `/Users/mikomac/…/Fala` | machine super-fallback | **Deleted** | Use `FALA_HOME` env or sibling `../Fala` |
| Python `_atomic_*` compose graphs / `LOKAY_USE_FALA` | super-fallback | **Deleted** | Fala is the sole composer; terminal outputs normalize public results |
| `PLACEHOLDER_PYTHON` / tomli shim | legacy | **Deleted** (#17) | Only `PLACEHOLDER_PROJECT` remains |
| Agent `or "grok"` / plan-as-success | silent invent | **Deleted** (#18) | Fail closed; see `NO_STUBS.md` |
| `always_approve` / `max_self_repair_attempts` knobs | unused lying config | **Deleted** | `--approve` lives in `executor.args`; recovery is one Fala path + 4-of-5 quorum |
| `lokay-run-grok` | named alias | **Deleted** | Use `lokay-run-agent` only |
| `LOKAY_USE_FALA` dual engine | runtime fallback | **Deleted** | Fala is always the composer |
| `find_default_package` candidates | package discover | **Promote** | env → repo `fala/` → packaged `data/` |
| `append_event` best-effort `except` | telemetry | **Promote** | State log must not abort mill; documented |
| `FALA_HOME` + optional sibling `../Fala` source fallback | Mojo runtime lookup | **Keep** | Python package stays tag-pinned; native source lookup is separate and has no user-specific hardcode |
| Dual `fala/` + `src/lokay/data/` package | packaging | **Promote** | Keep identical; hatch ships `data/` |

## Enforcement tests

- `tests/test_fallbacks_inventory.py` — locks deletions and Fala fail-closed.
- `tests/test_fala_package_lock.py` — checkout `fala/` and packaged `data/` are byte-identical.
- `tests/test_graph.py` — no `PLACEHOLDER_PYTHON` rewrite.
- `tests/test_agent_no_stub.py` — no silent agent defaults.

## Anti-patterns (do not reintroduce)

- Backward-compat re-exports with no callers.
- `except Exception: pass` then a second engine.
- Absolute home-directory paths for a single machine.
- Silent invent of harness/command/model names.
