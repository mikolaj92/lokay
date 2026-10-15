| Rule | Enforcement |
| --- | --- |
| Plan → Build → Check → Fix → Merge; only Merge ends a run | `graph.step`, `tick.act` |
| Decisions return probabilities, not prose | `effects.decide._check` |
| LLM and code steps return `result`; decisions return `next` | `tick`, `plan.verdict`, `check.aggregate` |
| Retry failed steps, recheck revised plans, return Fix to Check | `tick._retry`, `tick._plan_graph`, `graph.step` |
| `pi -p` writes production code | `build.build_code`, `fix.fix_code` |
| Only `store.py` writes persisted state | `store.save`, `store.write_json` |
| Subprocess execution stays in `effects/` | `lokay lint` |
| No new comments, docstrings, unit tests, or blanket staging | `lokay lint`, `checks.run_checks` |
| Recorded replay or a real run proves behavior | `scripts/check.sh`, `lokay replay` |
| Auto-merge stays on; only the nuke PR needs human approval | `config.load_repos`, `effects.gh.merge` |
| Do not import `lokay` from `src/lokay` | `scripts/check.sh` isolated import check |
