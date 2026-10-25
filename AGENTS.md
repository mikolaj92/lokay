| Rule | Enforcement |
| --- | --- |
| Plan → Build → Check → Fix → Merge; only Merge ends a run; infeasible → split + Retro | `graph.step`, `tick.act` |
| Decisions return probabilities, not prose | `effects.decide._check` |
| LLM and code steps return `result`; decisions return `next` | `tick`, `plan.verdict`, `review.verdict` |
| Retry failed steps; Plan classifies difficulty; harness2 runs Build/Fix and persists a per-repo library; Fix returns to Check | `tick._retry`, `h2.run_issue`, `graph.step` |
| Issue body is the spec; changed existing tests must be explicitly named there; no plan file lists | `checks.weakened_tests`, `h2.LokayAdapter` |
| Only `store.py` writes persisted state | `store.save`, `store.write_json` |
| Subprocess execution stays in `effects/` | `lokay lint` |
| No new comments, docstrings, unit tests, blanket staging, or label state; only remove existing lokay-* labels | `lokay lint`, `checks.run_checks` |
| Recorded replay or a real run proves behavior | `scripts/check.sh`, `lokay replay` |
| Auto-merge stays on; only the nuke PR needs human approval | `config.load_repos`, `effects.gh.merge` |
| Do not import `lokay` from `src/lokay` | `scripts/check.sh` isolated import check |
