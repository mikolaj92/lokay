# Lokay — ciała działów (Werdykt D, landed)

Status: wdrożone. Pięć działów to authored children. Agenci zostają
liśćmi wysokiej entropii wewnątrz tych dzieci. Parent geometry bez zmian.

## Rzut złożony: ten sam obiekt

To jest ten sam Lokay: jeden produktowy graf Fali, którego kolejność, bramki,
powroty i Definition of Done nie zależą od wykonawcy węzła. `factory_pass`
zostaje parentem pięciu działów, a `reap_stale_worktrees` pozostaje jego
niezależnym siblingiem. Ciało działu jest authored child Fala, nie agentem
działu. Done nie znaczy „agent odpowiedział”, „tick przeszedł” ani „plan
istnieje”; Done to jakościowy kod na `origin/main`, po merge i zamknięciu
powiązanego issue.

## Stan live

Live binding parenta jest w `src/lokay/organ/departments_boundary.py`.
Wrappery `src/lokay/proc/run_*_department.py` wołają child paths z
`fala/lokay.fala-package.toml`. Flaga `departments.agent_bodies` i runtime
`agent_*_department` zostały usunięte.

| Dział | Ciało live | Child | Agenci |
| --- | --- | --- | --- |
| `self_repair` | `run_path("self_repair_department")` | incident + `self_repair` | `self_repair_run_agent` tylko w slocie naprawy |
| `issue_triage` | `run_path("issue_triage_department")` | `issue_sieve_rows` → `issue_triage` | `issue_triage_agent` dopiero po `hard_facts` |
| `executor` | `run_path("executor_department")` | `executor_rows` → `issue_to_pr` | `run_agent` w `coding_execution`; executor nie merge’uje |
| `pr_triage` | `run_path("pr_triage_department")` | `pr_triage` z `pr_merge` + `close_issue` | opcjonalny `pr_review_agent` jako liść review |
| `pr_repair` | child `pr_repair` | test, diff, push, budżet | agent naprawy jako liść; merge zostaje w `pr_triage` |

Agent nie zastępuje efektora `pr_merge` ani `close_issue` polem `verdict`.

## Occupancy

Covering OPEN PR jest pracą `pr_triage`, nie nowym executorem.
`occupancy_catalog` + `inspect_live_receipt_issue` kończą leftover wrapper
przy covering PR. `issue_to_pr` zbiera existing delivery i idzie w closeout,
nie w drugi coding slot.

## Poza zakresem

- Drugi parent ani unroll ~520 atomów do `factory_pass`.
- Przywracanie department-wide agentów.
- GitHub Actions; weryfikacja i wykonanie pozostają lokalne.
- `ai:ready` / `work:ready` jako kolejka produktu.
