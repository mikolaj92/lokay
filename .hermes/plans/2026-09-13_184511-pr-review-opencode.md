# OpenCodeReview PR-review plugin — Implementation Plan

> **For Hermes:** Implement this plan sequentially; do not dispatch parallel agents.

**Goal:** Add Alibaba OpenCodeReview as a replaceable, separate-process Lokay PR-review plugin while preserving the task → implementation → PR → review → repair(task + findings) → new SHA → re-review → merge loop.

**Architecture:** The plugin analyzes an exact, isolated PR diff and returns a versioned, vendor-neutral JSON result. Lokay/Fala retains routing, policy, GitHub publication, repair, merge, and Done; findings are untrusted repair input and every new head SHA requires a fresh review. Keep existing Fala departments and serial geometry; any routing change starts with a README Mermaid update and review.

**Tech Stack:** Lokay/Fala, Unix subprocess + JSON contracts, Python plugin adapter, pinned Alibaba OpenCodeReview CLI, GitHub CLI/API; local verification through `uv run`.

---

## Cel i Definition of Done

Dla każdego kwalifikowanego PR-a Lokay musi wykonać dokładnie tę pętlę:

```text
oryginalne issue/task
  → implementacja
  → PR
  → pr_triage: OpenCodeReview na dokładnym base/head SHA
      ├─ kompletne review bez findings → approve → checks/test gates → merge → zamknięcie issue → Done
      ├─ findings → pr_repair(task + pełne findings) → test/diff gates → push nowego SHA
      │            → następny factory pass → ponowne review nowego SHA
      └─ brak dowodów, niepełne/niepoprawne review, błąd silnika lub limit
           → fail-closed / ręczne rozstrzygnięcie
```

**Done nadal oznacza jakościowy kod scalony do `main`.** Review, poprawka, nowy PR SHA, zielone testy ani sam werdykt `approve` nie są Done.

Akceptacja wymaga wykazania testem end-to-end (na lokalnym, kontrolowanym repo), że:

1. reviewer ogląda dokładne SHA PR-a, a jego wynik jest z tym SHA związany;
2. `request_changes` zachowuje pełne, zlokalizowane findings i przekazuje do implementacji również oryginalne issue/task;
3. poprawka przechodzi istniejące gates, publikuje nowy SHA i wraca do review w następnym passie;
4. dopiero `approve` dla aktualnego SHA oraz pozostałe dotychczasowe bramki pozwalają na merge;
5. błąd review, nieznany format, niepełne pokrycie, brak tasku albo wyczerpany budżet nigdy nie przechodzą do merge.

## Kontekst repozytorium i granice zmian

Obecny graf już rozdziela `pr_triage_department` i `pr_repair_department`; drugi dział jest osobną pod-Falą i nie powinien być uruchamiany z wnętrza `pr_triage`. Implementacja ma zachować geometrię `factory_pass`, jego serialność i te dwa istniejące sloty. Zmiana dotyczy kontraktów, ciał atomów i powrotnej krawędzi opisanej w README — nie nowego schedulera, nowego department-agent ani nowego ukrytego grafu w Pythonie.

Istotne istniejące miejsca:

- `README.md` — autorytatywny Mermaid state machine; aktualizować i przejrzeć **przed** zmianą routingu.
- `fala/lokay.fala-package.toml` — authored ścieżki `pr_triage`, `pr_repair` i `factory_pass`; to Fala prowadzi kolejność.
- `src/lokay/organ/review_boundary.py`, `src/lokay/pr_review.py`, `src/lokay/proc/collect_pr_review_evidence.py`, `src/lokay/proc/publish_pr_review.py` — dzisiejszy review, evidence, walidacja, cache i publikacja.
- `src/lokay/proc/select_pr_repair_department.py`, `src/lokay/proc/run_parent_pr_repair_subflow.py`, `src/lokay/compose/pr_repair.py` — przekazanie werdyktu do osobnej pod-Fali naprawczej.
- `src/lokay/organ/pr_outcome.py` — `pr_repair_verdict` binding jest w tym module; nie istnieje osobny `src/lokay/proc/pr_repair_verdict.py`.
- `src/lokay/organ/repair_boundary.py`, `src/lokay/organ/agent.py`, `src/lokay/prompts.py`, `src/lokay/tool_contracts/pr_repair/prompt.md` — przygotowanie naprawy i prompt executora.
- `src/lokay/proc/pr_repair_receipts.py`, `src/lokay/config.py`, `config.example.yaml` — budżet automatycznych rund napraw.
- `pyproject.toml`, `src/lokay/proc/`, `src/lokay/organ/` — entrypointy i granice procesów Lokaya.

**Nie cofać ani nie nadpisywać istniejących, niezwiązanych zmian w worktree.** Na początku implementacji ponownie sprawdzić `git status --short --untracked-files=all`; podczas audytu planu jedynym widocznym wpisem był ten plik planu. Aktualizację diagramu scalić z bieżącą zawartością README, nie przywracać pliku do HEAD.

## Kontrakt pluginu review

Utworzyć niezależny pakiet, np. `plugins/pr_review_open_code_review/`, z własnym `pyproject.toml`, CLI i testami. Nie kopiować ani nie importować kodu Alibaba do `lokay`; uruchamiać przypięty upstream CLI. Nie importować prywatnych modułów `lokay` z pluginu. Proces przyjmuje jeden JSON request na stdin i zwraca jeden JSON envelope na stdout; diagnostyka trafia na stderr. Plugin nie używa GitHub API, nie publikuje komentarzy/etykiet i nie wykonuje merge’a.

### Request `lokay.review-request/1`

```json
{
  "schema": "lokay.review-request/1",
  "repo": "owner/name",
  "pr": 84,
  "head_ref": "ai/fix/42-example",
  "head_sha": "<exact PR head SHA>",
  "base_ref": "main",
  "base_ref_sha": "<exact PR target-ref tip>",
  "comparison_base_sha": "<merge-base(base_ref_sha, head_sha), exact PR diff base>",
  "repo_path": "<ephemeral read-only checkout pinned to head_sha>",
  "diff_paths": [{"path": "src/example.py", "old_path": "", "status": "modified"}],
  "diff_sha256": "<SHA256 of patch bytes from exact base/head refs>",
  "pr_title": "...",
  "pr_body": "...",
  "task": {
    "repo": "owner/name",
    "type": "Issue",
    "state": "OPEN",
    "number": 42,
    "title": "...",
    "body": "...",
    "url": "..."
  },
  "task_identity_sha256": "<Lokay hash of canonical task identity and content>"
}
```

`task` pochodzi z kanonicznego issue, nigdy z opisu PR-a ani tekstowego `Closes #...` zgadywanego przez model. Najpierw zweryfikować PR repository/number/head branch, a dla standardowej gałęzi wyprowadzić numer przez `issue_number_from_branch(branch, branch_prefix=cfg.branch_prefix)`. Pobierać issue przez GitHub GraphQL `repository(owner,name).issueOrPullRequest(number)`, wymagać `__typename == Issue`, `state == OPEN`, zgodnego numeru i repozytorium; `IssueOrPullRequest` jest unią Issue/PullRequest, więc numeric ID sam nie wystarcza.[18][22]
Gdy branch nie ma issue number, pobrać wszystkie strony `PullRequest.closingIssuesReferences(first:100, after:...)`, zaakceptować dokładnie jednego kandydata i ponownie sprawdzić `Issue`, stan OPEN, numer i to samo repo.[19][21]
Nie parsować PR body jako źródła tasku. Brak, zamknięty/usunięty issue, issue/PR-number collision, inne repo/number albo wieloznaczność → `fail_closed`; nie zastępować oryginalnego tasku streszczeniem buildera.

`task_identity_sha256` wylicza Lokay z canonical JSON pól `repo`, `type`, `state`, `number`, `title`, `body` i `url` (UTF-8, stabilne key ordering); przekazać go w request i wymagać identycznego echa w result. Cache hit i każde wejście do repair ponownie pobierają kanoniczny issue i porównują digest; zmieniony/zamknięty task oznacza fail-closed, nie użycie nieaktualnego tasku.

### Result `lokay.review-result/1`

```json
{
  "ok": true,
  "schema": "lokay.review-result/1",
  "engine": {"name": "open-code-review", "version": "v1.12.0", "binary_sha256": "<verified pinned binary digest>"},
  "repo": "owner/name",
  "pr": 84,
  "head_sha": "<same exact head SHA>",
  "base_ref_sha": "<same exact PR target ref tip>",
  "comparison_base_sha": "<same exact merge-base used by OCR>",
  "task_identity_sha256": "<same Lokay canonical issue identity/content digest from request>",
  "diff_sha256": "<same Lokay-computed exact patch digest>",
  "status": "complete",
  "findings": [
    {
      "path": "src/example.py",
      "start_line": 12,
      "end_line": 12,
      "category": "bug",
      "severity": "high",
      "content": "...",
      "existing_code": "...",
      "suggestion_code": "..."
    }
  ],
  "summary": "...",
  "evidence": {
    "manifest_schema": "ocr.run-manifest/v1",
    "operation": "review",
    "input_mode": "range",
    "requested_from": "<base_ref_sha passed to --from>",
    "requested_head": "<head_sha passed to --to>",
    "terminal_state": "complete",
    "resolved_base_sha": "<comparison_base_sha>",
    "resolved_head_sha": "<head_sha>",
    "exact_range": "<comparison_base_sha>..<head_sha>",
    "run_failure": null,
    "warning_count": 0,
    "tool_failure_count": 0,
    "budget_exceeded": false,
    "upstream_execution": {
      "ocr_version": "v1.12.0",
      "provider": "<configured provider>",
      "model": "<configured model>",
      "configured_concurrency": 1,
      "rule_config_sha256": "<manifest digest>",
      "runtime_config_sha256": "<manifest digest>"
    },
    "repository_identity_sha256": "<verified hash of canonical owner/repo origin>",
    "preview_sha256": "<sha256 of canonical normalized preview JSON>",
    "input_fingerprint_sha256": "<sha256 of canonical refs, task, diff, engine and review-config identity>"
  },
  "coverage": {
    "diff_paths": [{"path": "src/example.py", "old_path": "", "status": "modified"}],
    "reviewable_paths": [{"path": "src/example.py", "old_path": "", "status": "modified"}],
    "selected": [{"path": "src/example.py", "old_path": ""}],
    "completed": [{"path": "src/example.py", "old_path": ""}],
    "reused": [],
    "failed": [],
    "waived": [],
    "excluded": []
  }
}
```

Kontrakt jest neutralny względem vendora: plugin mapuje upstream preview, review run/manifest i comments do neutralnego wyniku, nie wypuszczając raw manifest/logs poza adapter. `ocr review --format json` zwraca comments i status/manifest; adapter ustawia neutral `ok:true` wyłącznie po pełnym mapowaniu, a błędy mapuje na allowlisted error code bez raw stderr/exception.[12][13]

`diff_paths` (z `path`, `old_path`, statusem rename-aware) i `diff_sha256` wylicza Lokay. Preview v1.12 zwraca entries z `will_review` i `exclude_reason`, bez `old_path`; adapter joinuje je z rename-aware Git inventory Lokaya.[9][10] Manifest coverage to object rows `item_id/path/old_path`, nie string arrays.[13] Normalizacja do neutralnych ścieżek zachowuje rename identity.

Wymagać `manifest.schema_version=ocr.run-manifest/v1`, `operation=review`, `input.mode=range` i `run_failure` absent/null. OCR v1.12 zapisuje literalne argumenty `--from`/`--to` jako `requested_from`/`requested_head`: w tym flow są to `base_ref_sha` i `head_sha`; `resolved_base` to `comparison_base_sha = merge-base(base_ref_sha, head_sha)`, a `resolved_head` to `head_sha`. Nie porównywać `requested_from` z `comparison_base_sha`.[3][8][13] Utworzyć review checkout z credential-free origin `https://github.com/{repo}.git`; wymagać niepustego `repository.identity_sha256` równego SHA256 canonical upstream origin identity `github.com/{repo}`. Missing/mismatch fail-close — bez fallbacku do niezweryfikowanej ścieżki checkout. Każdy `run_failure` object jest błędem.

`preview_sha256` liczy canonical UTF-8 JSON z normalized preview input/path/decision fields. `input_fingerprint_sha256` wylicza Lokay (nie upstream) z repo/PR/task identity, refs, exact diff digest, engine binary/version, zaufanej provider/model/rule/tools/configuration oraz zwróconych `rule_config_sha256`/`runtime_config_sha256` — bez credentials. Wymagać `upstream_execution.ocr_version == v1.12.0`, provider/model równych jawnej konfiguracji, `configured_concurrency == 1` i obu poprawnych hashy; uwzględnić je w durable evidence/cache identity.[23] Review parser ma w neutral evidence zwrócić `warning_count`, `tool_failure_count` i `budget_exceeded`, bez treści ostrzeżeń ani raw logs. Wymagać `status=complete`, manifest `terminal_state=complete`, `budget_exceeded=false`, `tool_failure_count=0`, `warning_count=0`, `coverage.failed=[]`, `coverage.waived=[]`, `coverage.selected` zgodne z preview `will_review`, `coverage.completed` identity-set równe `coverage.selected` identity-set oraz `coverage.reused=[]` (resume wyłączony).[12][13] Preview `reviewable_paths` są pochodnymi entries `will_review=true`; entries nie mają `old_path`, więc join z Lokay inventory musi zachować rename identity i odrzucać ambiguity. Diff scope ma się zgadzać poza jawnie sklasyfikowanymi deleted old-side-only paths. Każda inna preview-excluded ścieżka blokuje approve; empty reviewable set również fail-closed. Upstream `thinking` i raw logs są odrzucane.

Lokay waliduje schema, repo/PR, base/comparison/head SHA, diff/config fingerprints, status/evidence, ścieżki, linie, kategorie i severity. Nieznany neutral schema/enum, zła lokalizacja, drift, timeout, nonzero exit, stdout z prose, incomplete preview/manifest lub niepokryty changed path => fail-closed. OCR normalizuje surową severity/category do dozwolonych wartości przed JSON; adapter nie może twierdzić, że zachowuje surowe enum value.

### OpenCodeReview jako wymienialny silnik

Przypiąć release `v1.12.0` i SHA256 digest właściwego platform assetu; nie kopiować digestów między platformami.[2][20] Instalacja i konfiguracja lokalnie, bez GitHub Actions; lokalny preflight sprawdza upstreamowe Git `>= 2.41`.[7] Nie instalować silnika przy każdym passie.

Lokay config wskazuje plugin command/argv/timeout i niesekretny provider/model jawnie podawane przez OCR `--provider/--model`; operator dostarcza credentials wyłącznie przez allowlisted provider-specific env. OCR może czytać runtime config/environment i provider keys z własnego configu; uruchamiać je z dedykowanym trusted `HOME`, jawnie oczyszczonym/allowlistowanym env i configiem bez shell hooks.[6] Użyć oddzielnego writable session dir, bez interactive shell rc.

Przypiąć OCR flags jawnie: `--concurrency 1`, `--effort low|medium|high`, skończone per-group `--timeout`, skończone `--max-tokens-budget`, zaufane `--rule`/`--tools`, `--background-file` oraz format/audience. Nie deklarować `--max-tools` jako twardego limitu: v1.12 flagą można jedynie podnieść embedded cap.[3] Wymagać `summary.budget_exceeded != true`, `tool_calls.failure == 0`, pustych warnings oraz poprawnego manifest; exit `0` sam nie dowodzi kompletności, a max-token budget może zwrócić częściowy wynik, który blokuje approve.[12]

Plugin review runs in an isolated checkout pinned to immutable commit IDs. Lokay records `base_ref_sha` (PR target-ref tip) and `head_sha`, computes `comparison_base_sha = merge-base(base_ref_sha, head_sha)`, then passes the immutable full SHAs directly as OCR `--from <base_ref_sha> --to <head_sha>`; OCR itself computes `merge-base(from,to)..to`.[3][8] Require manifest `input.mode == range`, `requested_from == base_ref_sha`, `requested_head == head_sha`, `resolved_base == comparison_base_sha`, `resolved_head == head_sha`, and `exact_range == comparison_base_sha..head_sha`.[13] Do not set `--from` to `comparison_base_sha` unless changing the expected diff semantics. Independently compute Lokay's exact patch digest over `comparison_base_sha..head_sha`; absent/mismatched manifest endpoints or digest fail closed. Verify SHA refs exist immediately before preview and review, the checkout is clean/read-only, and the PR still has the same base/head after review. If pinning/resolution cannot be verified, fail closed.

```text
ocr review \
  --repo <isolated repo_path> \
  --from <base_ref_sha> --to <head_sha> \
  --format json --audience agent --concurrency 1 \
  --provider <pinned-provider> --model <pinned-model> \
  --background-file <trusted-task-and-PR-context.md> \
  --effort <low|medium|high> --timeout <minutes> \
  --max-tokens-budget <finite-token-budget> \
  --tools <audited-tools.json>
```

Preview is a separate invocation with the same repo, immutable `--from`/`--to`, background, rule, exclude and file-selection limits as review; capture stdout and stderr separately. Preview runs no LLM and emits no manifest/session ID, so it cannot validate provider credentials/model or `--tools`; those are validated on the actual review run and bound in Lokay's input fingerprint. Use only trusted explicit rules/background, finite limits, a fresh scratch directory for each invocation, and a fresh writable OCR `HOME`/session area for the actual review.

OCR range mode computes `merge-base(from,to)..to`.[3][8] Review JSON includes comments and a run manifest.[12]

Preview emits separate JSON without a manifest.[9]

Capture both outputs separately, validate manifest SHAs, map comments to Lokay's contract and discard `thinking`.[11][13]

Use concurrency=1. Built-in tools include `task_done`, `code_comment` (local CommentCollector), and read-only context tools; `code_comment` is not GitHub publication.[5][14] Task and PR text are untrusted input. The plugin has no GitHub token/API, publisher, or merge capability. v1.12 tool JSON uses `plan_task` and `main_task` booleans: install an audited allowlist excluding `task_done` only if natural termination remains correct and permitting the findings collector/read tools.[5] Keep `code_comment` as OCR's findings path; OS-sandbox collector/output and assert findings return only through JSON, not GitHub. Tool filtering alone is not read-only. OS network policy allows only the configured provider endpoint; telemetry and other egress are denied, with smoke coverage that denial does not break review.

Before review, run `ocr review --preview --format json --audience agent` with the same repo, immutable refs, background, rules/excludes and file-selection limits. Provider/model/`--tools` are not validated by preview. OCR v1.12 preview emits `files[]` (`path/status/insertions/deletions/will_review/exclude_reason`) without a manifest; `--background-file` is also read during preview.[3][10] Bind the trusted task/PR context digest into effective config. Hash canonical normalized preview; `will_review=true` forms the reviewable set. Preview entries omit `old_path`, so join by path/status to rename-aware Git inventory and reject ambiguous mappings. Any excluded changed path—binary, unsupported/default/user exclusion, too-large, test filtering or OCR ignore—blocks approval; only deleted old-side-only paths are an explicit non-reviewable exception. Empty reviewable set fails closed. OCR include rules do not expand the extension allowlist.[4][15] Lokay `diff_sha256` is SHA256 of `git diff --binary --full-index --no-ext-diff --no-textconv --find-renames --no-color <comparison_base_sha> <head_sha> --` bytes. Bind preview and review to refs, digest, binary version and effective config hashes; drift invalidates results. Capture each invocation in fresh scratch storage (preview has no session); nonzero exit, invalid JSON or stale output fails closed.

Validate run `status`, `manifest.schema_version`, `operation`, `input.mode`, requested/resolved refs, `terminal_state`, `run_failure`, warnings, `tool_calls.failure` and `summary.budget_exceeded`; only complete status/terminal with no warnings or tool failures proceeds to policy.[12][13] Preview has no manifest; both calls must exit zero and emit exactly one JSON document.[3]

Manifest coverage entries are objects (`item_id/path/old_path`); normalize rename-aware identity, reject duplicate/inconsistent IDs, compare selected with preview `will_review`, completed with selected, and require reused/failed/waived empty (resume disabled). Any uncovered path, non-complete terminal, warning/failure/budget, unknown neutral schema/enum or output drift fails closed. Require requested refs equal CLI refs, `resolved_base == comparison_base_sha`, `resolved_head == head_sha`, `exact_range == comparison_base_sha..head_sha`, and Lokay's independent patch digest.[13] Never infer coverage from summary/comments; an empty set cannot approve.

Uruchomić reviewer na exact checkout z OS sandbox blokującym jego write i oddzielnym writable ephemeral session HOME; trusted OCR config/tools/rules są readonly, bez shell rc i nieufnego global rule file. Nie przekazywać GH credentials ani `LOKAY_HEALTH_LEASE`. `--tools` redukuje registry do jawnego zestawu, lecz `code_comment` pozostaje aktywny jako lokalny CommentCollector/output, więc isolation gwarantuje OS sandbox i brak GitHub credentials, a nie deklaracja read-only tools.[5][14] Provider egress jest jedyną network capability. Test integracyjny potwierdza niezmienność checkout/refów, brak GitHub side effects i zgodność collector comments ze stdout.

OpenCodeReview zwraca comments/status, nie werdykt Lokaya.[12] Reguła Lokaya jest deterministyczna i testowana:

- Only upstream `complete`, full exact-SHA preview/coverage, and zero findings may produce `approve`.[3][9][13]
- **Every finding, including `low`, blocks and routes to `request_changes`.** OCR v1.12 normalizes unknown categories to `other` and severity to `low` before JSON serialization, so raw enum provenance is unavailable.[14] Findings retain normalized category/severity for repair context; low-only approve+nits stays disabled.
- Sygnał możliwego wycieku credentiala przechodzi przez deterministyczny secret gate, fail-closed/manual. Nie wnioskować tego z `category=security`; redagować matched secrets z content/suggestion/existing_code oraz persisted artifacts; nie logować raw OCR output.
- `request_changes` przenosi **wszystkie** findings, bez utraty `path`, zakresu linii, kategorii, severity, treści i ewentualnej sugestii;
- każda inna/nieznana/niepełna odpowiedź jest fail-closed — nigdy nie przekształca się w approve;
- test lokalny, checks, ocena merge oraz Definition of Done nadal należą do Lokaya, nie do OpenCodeReview.

Nie opierać decyzji na deklarowanych benchmarkach vendora. Przed aktywacją zmierzyć trafność i kompletność na wybranej próbce PR-ów Lokaya; upstream sam opisuje niższy recall względem agentów ogólnego przeznaczenia jako kompromis precision/recall, więc lokalny shadow review mierzy też missed findings.[1]

## Dokładna zmiana przepływu

1. `pr_triage` ładuje PR evidence: `head_sha`, `base_ref_sha`, independently-computed `comparison_base_sha`, branch/ref, checks, PR metadata i kanoniczny `task`; buduje exact in-scope diff paths + SHA256 digest.
2. Na ephemeral exact-SHA read-only checkout działa wybrany przez config plugin review. Plugin wykonuje preview i review przy zamrożonych refs/config; zwraca `review-result/1` z complete evidence albo error.
3. Lokay waliduje preview coverage, manifest, refs/digest, findings anchors i stosuje policy decision. Dopiero potem Lokay publikuje review; plugin nigdy nie ma publisher capability.
4. Przy `request_changes` werdykt review trafia przez `summarize_pr_triage_department` i `select_pr_repair_department` do **istniejącego** `run_pr_repair_department`. Zachować task w receipt/transferze, nie tylko decision/verdict.
5. `pr_repair` dostaje oba wejścia:
   - oryginalny task: repo, numer, tytuł, pełne body/acceptance criteria i URL;
   - findings: lista obiektów z dokładnymi plikami/liniami/priorytetem/uzasadnieniem, `reviewed_head_sha` i werdykt.
6. Prompt naprawy każe zachować wymagania tasku, usunąć wszystkie blokujące findings, uwzględnić nity według zakresu, dodać testy regresyjne i podać wynik testów. Task i review są danymi wejściowymi, nie uprawnieniami do merge’a/push; obecne gates real diff, test, commit i push pozostają obowiązkowe.
7. Repair publikuje nowy commit na PR branch. `factory_pass` kończy się normalnie. Następny pass review’uje nowy SHA od początku; cache nigdy nie przenosi approve ani findings między SHA.
8. `approve` przechodzi przez dotychczasowe checks i lokalne testy, następnie existing merge/close/receipt. `fail_closed`, niejednoznaczny task, review error i wyczerpany budżet parkują PR do ręcznego rozstrzygnięcia.

### Budżet rund

Obecny `pr_repair_receipts.resolve_budget()` używa `max_repairs_per_tick` jako **dożywotniego** limitu napraw danego PR-a; domyślna wartość `1` zatrzyma pętlę po pierwszej poprawce. Usunąć to sprzężenie. Użyć `max_request_changes_per_pr` jako jawnego limitu automatycznych prób naprawy na PR, domyślnie `2` (jak w `config.example.yaml`): po pierwszym i drugim `request_changes` dozwolone są repair #1 i repair #2; po drugiej naprawie nowy SHA musi przejść review, a jego trzecie `request_changes` eskaluje bez repair #3. Receipt nadal deduplikować po repo/PR, trzymać last reviewed/repaired SHA i nie otwierać pętli bez postępu. Naprawić crash consistency: parent obecnie stempluje attempt po każdym compose result, także po błędzie; liczyć tylko potwierdzoną próbę z prawidłowym `repair` terminal/repaired SHA, a błędny/skipped compose fail-close/manual bez fałszywego sukcesu ani automatycznego retry thrash.

## Plan prac

Każda zmiana kodu idzie pionowym TDD: dodać jeden test zachowania → uruchomić i potwierdzić oczekiwany RED → minimalna implementacja → GREEN → refactor. Nie pisać całego zestawu testów z wyprzedzeniem i nie scalać szerokich etapów w jeden commit. Diagram jest wyjątkiem kolejności: aktualizacja i review Mermaid poprzedzają zmiany routingu Fali.

### Etap 1 — diagram i przejścia

1. Zaktualizować Mermaid w `README.md` jako pierwszy krok: `request_changes → triage receipt → factory parent → pr_repair(task + findings) → new SHA → next-pass review`; osobno `approve → existing checks/test/merge` oraz `fail-closed → manual`.
2. Dodać/uzupełnić opis, że `pr_triage` **nie uruchamia kodera**; rodzic uruchamia oddzielny dział. Nie unrollować rodzica ani nie zmieniać kolejności pięciu działów.
3. Przejrzeć spójność diagramu z obecnym `fala/lokay.fala-package.toml`; parent nadal tylko wywołuje department-child.
4. Add a RED test for README/path-table synchronization and review-result/repair/approve/fail-closed transitions. Run RED, then `uv run lokay-readme-check` and `uv run pytest -q tests/test_readme_state_machine.py tests/graphs/factory_pass/test_graph.py tests/graphs/factory_pass/test_transitions.py`. After reviewing the diagram, preserve Fala parent geometry/order, existing department slots, and serial flow.

### Etap 2 — kontrakt i upstream fixtures

1. W `plugins/pr_review_open_code_review/tests/test_contract.py` dodać RED na fixture upstream v1.12 JSON → neutral `lokay.review-result/1`; finding zachowuje path, start/end line, category, severity, content i suggestion code, a `thinking` jest usunięte.
2. Dodać RED/GREEN testy manifest schema/version, refs (`requested_from=base_ref_sha`, `requested_head=head_sha`, `resolved_base=comparison_base_sha`, `resolved_head=head_sha`), execution version/provider/model/concurrency/config hashes, terminal state, preview/run binding i rename-aware coverage identity sets: selected odpowiada preview `will_review`, completed == selected, reused/failed/waived puste, brak `run_failure`. Oddziel fixtures preview JSON, review JSON + manifest i neutral result; preview nie ma manifest/session ID ani nie waliduje provider/tool config. Pin fixtures do upstream v1.12 output shape.
3. Dodać RED/GREEN dla terminal state `partial/failed/skipped`, run_failure, incomplete preview, każde exclusion, preview `exclude_reason=too_large`, manifest `coverage.failed[].classification=budget`, warnings/coverage truncation, missing manifest, malformed JSON, unknown neutral schema/enum, repo/PR/SHA mismatch i invalid path/range. Żaden przypadek nie może stać się approve. Każda excluded source path blokuje full coverage; deleted old-side-only paths to jawny wyjątek, nie selected. V1.12 normalizuje category/severity przed JSON; każde finding, także `low`, blokuje.
4. Dodać schema fixtures pod `plugins/pr_review_open_code_review/tests/fixtures/`; fixture nie zawiera sekretów ani vendor `thinking`.

### Etap 3 — osobny plugin OpenCodeReview

1. W `plugins/pr_review_open_code_review/tests/test_cli.py` dodać RED dla request→argv construction i kontrolowanego runnera; `tests/test_contract.py` weryfikuje result envelope.
2. Utworzyć `plugins/pr_review_open_code_review/pyproject.toml` i mały stdlib-only CLI, bez zależności/importu `lokay`, GitHub API, komentarzy i merge capabilities.
3. GREEN: argv bez shella, `--repo`, immutable `--from <base_ref_sha> --to <head_sha>`, `--format json`, `--audience agent`, `--concurrency 1`, jawne `--provider/--model`, `--background-file` z oryginalnym taskiem/PR i custom tools JSON. Oddzielne preview używa tego samego repo/ref/background/rule/exclude/file-selection config plus `--preview --format json --audience agent`; provider/model/tools waliduje faktyczny review run, nie preview. Przed implementacją zweryfikować v1.12 flag compatibility z fixture/help. Timeout/nonzero/malformed/oversized stdout (ustalić limit, np. 16 MiB) zwraca `fail_closed`; stderr tylko diagnostyczny.
4. `--tools` wyłącza embedded tool registry, ale zachowuje `code_comment` jako findings collector. Z pinned v1.12 JSON schema (`plan_task`, `main_task`, `definition`) utworzyć/testować jawny allowlist: read/context tools w plan i `code_comment` + read/context w main; wyłączyć `task_done` tylko jeśli runtime poprawnie obsługuje natural termination.[5] Nie nazywać tego read-only: `code_comment` zapisuje lokalny collector. OS sandbox blokuje write do checkout/git/refs/remotes; osobny session HOME writable, brak GitHub credentials. OS network policy allowlistuje provider endpoint i blokuje telemetry/pozostały egress. Smoke weryfikuje effective toolset, JSON findings, brak side effects i graceful denial niedozwolonego egress.
5. Bind allowlisted env (`PATH`, HOME/config dirs, capability marker, jawnie wskazane provider credential env); nigdy `GH_*`, `GITHUB_*`, `LOKAY_HEALTH_LEASE` ani ambient env wholesale. Osobne ephemeral HOME/session; zaufana konfiguracja providerów bez shell hooks `api_key_cmd`.
6. Dodać parser upstream preview+review → neutral result; usuwać `thinking` i raw logs. Testy argv/environment/timeout/status; brak CLI/provider nie ma fallbacku do starego agenta. Preflight (nie per pass) sprawdza dokładną wersję i Git ≥2.41; zweryfikować każdą platformową digest sumą z pinned release manifestu.

### Etap 4 — exact-SHA evidence i oryginalny task

1. Rozszerzyć `tests/test_pr_review_io.py`: RED dla PR `baseRefName/baseRefOid/headRefOid`, exact PR diff i task evidence; weryfikować same repo/PR/head branch, issue/PR-number collision, OPEN state i paginowane closing relations.
2. Rozszerzyć `src/lokay/pr_review_io.py`, `src/lokay/proc/collect_pr_review_evidence.py` i GitHub read helpers. Dla branch number preferować `issue_number_from_branch`; dla braku numeru użyć paginowanego GraphQL `closingIssuesReferences` i wymagać dokładnie jednego Issue. `repository.issueOrPullRequest(number)` musi zwrócić `__typename == Issue`, OPEN state, zgodne repo i numer. Zmienić fake/dry-run fixtures tak, by explicit test-mode Issue type był weryfikowany; zero/wiele/PR collision/non-OPEN/mismatch → fail-closed.
3. Testować osobny review checkout, OS sandbox zapisu, pinned `HEAD == head_sha` i exact base. Dodać `baseRefName/baseRefOid` do evidence fields; weryfikować preview file set i review manifest `input.requested_from/requested_head/resolved_base/resolved_head`. Preview jest osobnym JSON bez manifestu; run manifest pochodzi z review JSON. Checkout origin musi być credential-free `https://github.com/{repo}.git`; porównać OCR `repository.identity_sha256` ze SHA256 canonical `github.com/{repo}` i fail-close przy braku/mismatch. Po review ponownie odczytać PR head/base i fail-close przy drift; nie używać moving refs.
4. `--from <base_ref_sha> --to <head_sha>` używa merge-base semantics. Testować requested refs zgodne z CLI args oraz `resolved_base == comparison_base_sha = merge-base(base_ref_sha, head_sha)`; nie wymagać, by merge-base był równy tipowi base branch.
5. Uruchomić RED/GREEN dla task missing/ambiguous, branch-number mismatch, issue/PR collision, znikniętego/zamkniętego/zmienionego issue, niekompletnej closing-relation pagination, base/head drift i dirty/writable checkout. Tylko pełny, dokładny input dopuszcza plugin.

### Etap 5 — provider seam i werdykt Lokaya

- [x] Napisać test atomu Lokaya, który wysyła JSON request do skonfigurowanego procesu i waliduje jeden JSON response; dodać root `project.scripts` entrypoint i mały subprocess atom. Process boundary jest jawny i nie ma fallbacku do starego reviewer-agenta.
- [x] Przed zmianą live routing zaktualizowano i sprawdzono Mermaid review-result/fail-closed w README; body istniejącego slotu `pr_review_agent`/boundary używa niezależnego pluginu, bez nowego węzła orchestration.
- [x] Structured findings mają deterministyczną Lokay policy: kompletne zero findings → approve, każde finding (także `low`) → `request_changes`, wrong SHA/incomplete/error → fail-closed.
- [x] Nie ma generatywnego retry dla plugin-result; nieobsłużona potrzeba additional evidence fail-closes.
- [x] Live config wymaga pluginu i pinów, a bypass nie produkuje approvals.

### Etap 6 — publikacja line-level i cache po restarcie

**Decyzja API przed implementacją:** obecny `comment_pr()` publikuje conversation comment, nie inline review thread. Przed natywnym inline review potwierdzić GitHub review API payload/permissions oraz `commit_id` + diff-side `line`/side semantics na testowym repo. Jeśli capability/token tego nie obsługuje, publikować wszystkie findings w jednym idempotentnym PR conversation comment; każdy wadliwy anchor nadal fail-close.

- [x] Lokay publikuje SHA-bound PR conversation comment z verdict/markerem, artifact digest i pełnymi findings; plugin nie ma GitHub auth. Native inline review pozostaje niezrealizowane i wymaga autoryzowanego API acceptance.
- [x] Immutable, redacted full-result artifact zapisuje się atomowo przed publikacją; marker/cache wiąże pełny SHA, result i artifact digest. Cache rewaliduje aktualny PR i kanoniczny OPEN task; invalid/missing artifact oznacza fresh review.
- [x] Odzyskiwanie cache odtwarza komplet findings/task i weryfikuje refs, diff/config, engine, preview/input fingerprint oraz upstream rule/runtime config digest. Sprzeczny lub niekompletny cache nie zatwierdza.

### Etap 7 — task + findings do kodera

- [x] Kanoniczny Issue i pełne findings przechodzą przez triage receipt, `select_pr_repair_department` i istniejący parent; niepełny/mismatch handoff fail-closes.
- [x] `pr_repair` dostaje oryginalny task, pełne findings, reviewed/start SHA i task/result digests; prompt oznacza treść jako niezaufaną i nie daje push/merge authority.
- [x] Review-repair ponownie rozwiązuje OPEN Issue bezpośrednio przed `compose_pr_repair`; digest/content drift blokuje uruchomienie workera.

### Etap 8 — bounded review→repair loop

- [x] `max_request_changes_per_pr=2` ogranicza potwierdzone repair attempts; każdy nowy SHA nadal jest review’owany, a cap nie blokuje approve.
- [x] Markery liczą unikalne request_changes head SHA; repair receipts liczą jedynie potwierdzone nowe pushed SHA; błędny/skipped result nie zużywa budżetu.
- [x] Review repair wymaga start SHA == reviewed SHA; CI repair wymaga stabilnego checks head, zgodnego remote PR head i czystego local HEAD. Fork repair jest jawnie unsupported i fail-closed.
- [x] Acceptance sequence sprawdza dwa findings→repair cykle z wejściem na start SHA, confirmation remote new SHA, fresh review na SHA-2/SHA-3, brak cache na SHA-3, eskalację findings po cap i approve SHA-3 prowadzące do pojedynczego merge.

### Etap 9 — konfiguracja, shadow evaluation, aktywacja

- [x] Config parse/validate wymaga skonfigurowanego procesu, HTTPS provider, model, trusted config/binary digest, plików i sandboxu dla live merge.
- [ ] Dostarczyć i zweryfikować platformowo przypiętą OpenCodeReview v1.12.0 binary/provider/sandbox configuration; `config.yaml` nie zostało zmienione.
- [ ] Shadow pilot dla kontrolowanego zestawu historycznych PR SHA; porównać precision/recall, linie, coverage, czas i koszt z ludzką adjudication.
- [ ] Aktywować live engine dopiero po shadow acceptance; do tego czasu live acceptance jest zablokowany, bez starego reviewer fallbacku.


## Oczekiwane pliki

**Nowe (proponowane):**

- `plugins/pr_review_open_code_review/pyproject.toml`
- `plugins/pr_review_open_code_review/src/lokay_review_open_code_review/` — niezależny, stdlib-only adapter/CLI
- `plugins/pr_review_open_code_review/tests/fixtures/upstream_v1_12/` — success/partial/skipped, preview exclusions i manifest fixtures
- `plugins/pr_review_open_code_review/tests/` — parser/contract/CLI tests
- root Lokay atom + `project.scripts` binding dla JSON process boundary, `src/lokay/config.py` schema/validation, config example i redacted durable review/repair receipts

**Modyfikowane prawdopodobnie:**

- `README.md`
- `docs/GRAPH.md` — aktualizacja starych twierdzeń, że `max_repairs_per_tick` jest dożywotnim per-PR limitem
- `fala/lokay.fala-package.toml` i byte-identical `src/lokay/data/lokay.fala-package.toml` — jeśli authored Fala description wymaga zmiany; parent geometry pozostaje, a package-lock test musi przejść
- `config.example.yaml`, ewentualnie `config.yaml` wyłącznie po osobnej zgodzie/operatorowym ustawieniu
- `pyproject.toml`
- `src/lokay/pr_review.py`, `src/lokay/pr_review_io.py`, `src/lokay/review_boundary.py`
- `src/lokay/proc/collect_pr_review_evidence.py`, `publish_pr_review.py`, `summarize_pr_triage_department.py`, `select_pr_repair_department.py`, `run_parent_pr_repair_subflow.py`, `pr_repair_receipts.py`
- `src/lokay/organ/review_boundary.py`, `repair_boundary.py`, `agent.py`
- `src/lokay/config.py`, `config.example.yaml`, `tests/test_config_and_tick.py` — review provider/plugin command schema i validation
- `src/lokay/prompts.py`, `src/lokay/tool_contracts/pr_repair/prompt.md`
- `tests/test_pr_review.py`, `tests/test_pr_review_io.py`, `tests/test_review_boundary.py`, `tests/test_pr_repair.py`, `tests/test_pr_repair_fala.py`, `tests/test_pr_repair_budget_receipt.py`, `tests/test_readme_state_machine.py`, `tests/test_config_and_tick.py`, `tests/test_fala_package_lock.py`, `tests/graphs/pr_triage/`, `tests/graphs/pr_repair/`, `tests/graphs/factory_pass/`

## Lokalne testy i acceptance

Uruchamiać testy stopniowo, potem pełny zestaw:

```bash
uv run pytest -q plugins/pr_review_open_code_review/tests
uv run pytest -q tests/test_pr_review.py tests/test_review_boundary.py tests/test_pr_review_io.py tests/test_readme_state_machine.py
uv run pytest -q tests/test_pr_repair.py tests/test_pr_repair_fala.py tests/test_pr_repair_budget_receipt.py tests/graphs/pr_triage tests/graphs/pr_repair tests/graphs/factory_pass
uv run pytest -q tests/test_config_and_tick.py tests/test_fala_package_lock.py
uv run lokay-readme-check
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
uv run pytest -q
```

CLI smoke (lokalna, skonfigurowana maszyna; nie logować klucza):

```bash
ocr version                 # oczekiwana wersja przypięta w plugin config
ocr llm test                # łączność provider/model (tylko jawny preflight)
uv run lokay path --describe
```

`ocr llm test` wysyła pojedyncze testowe żądanie chat do skonfigurowanego providera; uruchamiać wyłącznie za zgodą operatora, z kontrolowanym kosztem i bez zapisywania odpowiedzi/sekretów w logach.[3]

W lokalnym repo testowym zasymulować trzy factory passes bez realnego GitHub side effectu: (1) findings → task+findings docierają do repair; (2) nowy SHA po repair → plugin review wykonywany ponownie; (3) approve na tym nowym SHA + green gates → merge branch wykonuje się tylko raz. Dodatkowo: błąd pluginu, zły SHA, zły anchor, brak issue, invalid/partial JSON, wyczerpany cap i crash po publikacji review muszą zakończyć się fail-closed/idempotentnie.

## Ryzyka i decyzje

- **Werdykt upstreamu:** JSON OpenCodeReview niesie comments/status, nie Lokay approve/request_changes. Werdykt i próg nits są Lokay-owned, jawne i testowane.[12][13]
- **Coverage:** Preview returns per-path `will_review` decisions; manifest coverage is path-object sets. Rename/deletion identities and every pre-dispatch exclusion must be joined to Lokay's full diff inventory; `complete` alone does not prove full diff coverage.[4][9][13]
- **Publikacja/linie:** obecny `publish_review()` używa `gh pr comment`, nie review/inline endpoint. Natywne inline wymaga osobnej publication capability oraz integration testu `commit_id` i diff-side line/side; w przeciwnym razie publikować wszystkie findings w jednym conversation comment. Anchor niemożliwy/nieprzyjmowany nie usuwa findingu; blokuje auto-merge, pełny finding pozostaje w durable artifact.
- **Crash/resume:** po opublikowaniu review i przed `pr_repair` następny pass musi odzyskać wszystkie findings dla tego SHA i oryginalny task; marker zawierający sam verdict jest niewystarczający. Obecnie `load_pr_evidence()` pobiera PR conversation `comments`, a nie review threads/inline review API, więc pełną trwałość zapewnić własnym, idempotentnym body artifact/receipt (z digestem) albo dedykowanym read path; nie zakładać, że PR conversation comments zawierają inline findings.
- **Licznik rund:** `max_request_changes_per_pr` ogranicza zakończone próby repair, a nie review-markers; po wykorzystaniu limitu nadal review’ować nowy SHA i pozwolić mu na approve, ale eskalować jego kolejne `request_changes` bez repair. Pełny sequence test jest rozstrzygający.
- **Klucze/model:** OCR ma osobny config i provider API; konfiguracja LaunchAgenta jawnie przekazuje provider/model i dozwolone credentials, bez zależności od interaktywnego TUI/shell.[3][6]
- **Wartość review:** upstream publikuje benchmarky, ale decyzję o domyślnym uruchomieniu poprzedza lokalna ocena historycznych PR-ów i dokładności anchorów.[1]
- **Licencja/dystrybucja:** używać przypiętego release/CLI jako procesu zewnętrznego, nie kopiować kodu do Lokaya; upstream publikuje licencję Apache-2.0.[17]

## Sources

[1] https://github.com/alibaba/open-code-review
    > "It reads Git diffs, sends changed files to a configurable LLM via an agent with tool-use capabilities, and generates structured review comments with line-level precision."
    > "Note that its Recall is lower than general-purpose agents"
[2] https://api.github.com/repos/alibaba/open-code-review/releases/tags/v1.12.0
    > ""size": 54911810, "digest": "sha256:92601579180aacc61d2d2861773271ddd03d6d5d3a2ac2bea553d883def81cf2""
[3] https://github.com/alibaba/open-code-review/blob/v1.12.0/pages/src/content/docs/en/cli-reference.md
    > "| `--from <ref>` | — | — | Source ref to start the diff from (e.g., `main`). |"
    > "When set, OCR computes `merge-base(from, to)..to`."
    > "Run the filter pipeline but skip the LLM."
    > "Path to a custom JSON review rule file."
    > "Names under both `providers` and `custom_providers` are accepted."
    > "Path to a custom JSON review rule file"
    > "OCR computes merge-base(main, feature-branch)..feature-branch"
    > "Run the filter pipeline but skip the LLM"
    > "Resolves the LLM endpoint exactly the way `ocr review` does, sends a single canned chat request"
[4] https://github.com/alibaba/open-code-review/blob/v1.12.0/pages/src/content/docs/en/review-rules.md
    > "files not matching any `include` pattern still proceed"
    > "files not matching any `include` pattern still proceed through the `unsupported_ext` and `default_path` checks"
    > "excludes the file as `too_large`"
    > "The filter is a five-gate algorithm"
    > "Files that survive all five gates are sent to the LLM"
[5] https://github.com/alibaba/open-code-review/blob/v1.12.0/pages/src/content/docs/en/tools.md
    > "Context tools are read-only context, not comment targets."
    > "When the agent sees `task_done`, it stops calling the LLM and starts processing accumulated `code_comment` calls."
[6] https://github.com/alibaba/open-code-review/blob/v1.12.0/pages/src/content/docs/en/configuration.md
    > "If `providers.<name>.api_key` is unset, OCR falls back to the corresponding environment variable."
[7] https://github.com/alibaba/open-code-review/blob/v1.12.0/pages/src/content/docs/en/quickstart.md
    > "Git ≥ 2.41"
[8] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/diff/git.go
    > "base = merge-base(from,to); head = the commit `to` resolves to;"
    > "RemoteIdentity returns a stable, credential-free identity string"
[9] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/agent/preview.go
    > "without dispatching any"
[10] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/model/preview.go
    > "WillReview    bool          `json:"will_review"`"
[11] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/model/review.go
    > "StartLine      int    `json:"start_line"`"
[12] https://github.com/alibaba/open-code-review/blob/v1.12.0/cmd/opencodereview/output.go
    > "Comments       []model.LlmComment    `json:"comments"`"
    > "The status set above is therefore the single source of truth"
[13] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/session/manifest.go
    > "RunManifest is the immutable, versioned coverage snapshot of a single run."
    > "selected must be the disjoint union of the four terminal sets"
    > "RemoteIdentity returns a stable, credential-free identity string for the"
    > "ManifestSchemaVersion identifies the versioned, machine-readable coverage"
[14] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/tool/code_comment.go
    > "CodeCommentProvider submits review comments to the per-Agent CommentCollector."
    > "func normalizeCodeCommentSeverity(severity string) string { normalized := strings.ToLower(severity) if _, ok := validCodeCommentSeverities[normalized]; ok { return normalized } return codeCommentSeverityLow }"
    > "func normalizeCodeCommentCategory(category string) string { normalized := strings.ToLower(category) if _, ok := validCodeCommentCategories[normalized]; ok { return normalized } return codeCommentCategoryOther }"
[15] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/config/allowlist/allowed_ext.go
    > "IsAllowedExt returns true when the given file extension is in the supported types list."
[17] https://github.com/alibaba/open-code-review/blob/v1.12.0/LICENSE
    > "Licensed under the Apache License, Version 2.0 (the "License");"
[18] https://docs.github.com/en/rest/issues/issues
    > "You can identify pull requests by the pull_request key."
[19] https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
    > "You can manually link up to ten issues to each pull request."
[20] https://github.com/alibaba/open-code-review/releases/tag/v1.12.0
    > ""tag_name": "v1.12.0", "target_commitish": "main""
[21] https://docs.github.com/en/graphql/reference/pulls
    > "List of issues that may be closed by this pull request."
[22] https://docs.github.com/en/graphql/reference/issues
    > "Possible types for IssueOrPullRequest Issue PullRequest"
    > "An Issue is a place to discuss ideas, enhancements, tasks, and bugs for a project."
    > "An Issue is a place to discuss ideas, enhancements, tasks, and bugs for a project"
[23] https://github.com/alibaba/open-code-review/blob/v1.12.0/internal/agent/agent.go
    > "runtimeConfigSHA256 is the deterministic identity of the allowlisted, non-secret"
    > "// runtime settings: protocol, model, sanitized endpoint host, language, per-request"
    > "// runtimeConfigSHA256 is the deterministic identity of the allowlisted, non-secret"
