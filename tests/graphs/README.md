# Graph test inventory

The expanded Fala catalog is the authority for generated graph suites. Native tests drive `host_run_package` with a FEP/1 fixture organ. `host_drive` with pre-registered outputs is not a `when` proof.

- Paths: **46**
- Expanded nodes and per-node suites: **626**
- Conduction edges: **1391**
- `when` branches: **246**
- Authored effectors with `output_schema`: **554** / missing **0**.
- Authored (before expansion): 526 nodes / 1170 edges / 222 `when` branches.

Each path has `test_<atom>.py`, `test_transitions.py`, and `test_graph.py`. The audit compares node metadata and transition metadata against `fala/lokay.expanded.golden.json`; it does not treat file names as proof of execution.

| Path | Nodes | Edges | `when` |
|---|---:|---:|---:|
| `daemon_cycle` | 6 | 9 | 3 |
| `factory_pass` | 17 | 43 | 6 |
| `issue_to_pr` | 9 | 17 | 3 |
| `issue_to_pr_delivery` | 38 | 147 | 26 |
| `coding_execution` | 16 | 31 | 9 |
| `local_repair_execution` | 11 | 23 | 5 |
| `issue_triage` | 26 | 71 | 15 |
| `issue_split` | 13 | 42 | 10 |
| `pr_repair` | 38 | 95 | 28 |
| `pr_triage` | 27 | 75 | 18 |
| `self_repair` | 9 | 15 | 0 |
| `stale_worktree_reap` | 3 | 3 | 0 |
| `implementation_dispatch` | 20 | 42 | 12 |
| `triage_dispatch` | 7 | 8 | 2 |
| `queue_conflict` | 14 | 23 | 5 |
| `select_implement` | 4 | 3 | 0 |
| `self_repair_prepare` | 27 | 48 | 12 |
| `self_repair_validate` | 16 | 18 | 11 |
| `closeout_pr` | 18 | 38 | 6 |
| `ready_hygiene` | 3 | 2 | 0 |
| `product_pass_budget` | 74 | 143 | 16 |
| `test_local_execution` | 14 | 46 | 6 |
| `leftover_closeout` | 3 | 2 | 0 |
| `factory_begin` | 14 | 27 | 0 |
| `localize_execution` | 15 | 33 | 2 |
| `relocalize_off_goal` | 18 | 37 | 4 |
| `assert_real_diff_execution` | 10 | 21 | 0 |
| `self_repair_activate_execution` | 14 | 37 | 7 |
| `status_snapshot` | 12 | 20 | 1 |
| `pr_create_execution` | 7 | 13 | 2 |
| `stage_label_execution` | 8 | 17 | 2 |
| `plan_issue_execution` | 6 | 12 | 1 |
| `intake_check_execution` | 14 | 36 | 8 |
| `daemon_entry` | 4 | 5 | 2 |
| `self_repair_entry` | 11 | 22 | 5 |
| `child_harvest` | 10 | 9 | 0 |
| `product_entry` | 3 | 3 | 1 |
| `self_repair_department` | 2 | 1 | 1 |
| `issue_triage_department` | 3 | 3 | 0 |
| `issue_sieve_row` | 5 | 8 | 2 |
| `issue_sieve_rows` | 17 | 48 | 5 |
| `executor_department` | 3 | 3 | 0 |
| `executor_rows` | 26 | 78 | 8 |
| `executor_row` | 5 | 7 | 1 |
| `pr_triage_department` | 5 | 7 | 1 |
| `cross_repo_release_train` | 1 | 0 | 0 |
