# Issue ledger — decyzje, nie cache faktów

GitHub Issue jest księgą **decyzji**. Etykiety `ai:*` na issue to wyłącznie to, czego nie da się wyliczyć z GitHuba. Agent nie ustawia etykiet. In-flight (job, PR, checki) nie jest stanem issue.

## Stany (decyzje)

| Stan | Etykieta | Kto widzi | Co wolno |
| --- | --- | --- | --- |
| **undecided** | brak etykiety decyzyjnej | `list_inbox` | triage **oraz** `issue_to_pr` — otwarte issue jest pracą; `work:ready` nie jest bramką |
| **ready** | otwarte issue (ślad `ai:ready` / `work:ready` opcjonalny) | `list_ready` / `survey_ready` (pełna strona, nie newest-50) | `issue_to_pr`, o ile brak human stop, żywego joba i covering open PR |
| **blocked** | `ai:blocked` | nikt | człowiek |
| **needs-feedback** | `ai:needs-feedback` | nikt | człowiek |
| **parked** | `frozen` / `ai:frozen` / `ai:tracker` | nikt | człowiek / rodzic splitu |
| **closed** | issue closed | nikt | koniec |

Otwarte issue **jest kolejką**. `ai:ready` / `work:ready` są **śladem ledgeru**, nie biletem wstępu. Wejście to otwarte issue na repo z katalogu. Human stop (`ai:blocked` / `ai:needs-feedback` / park) wyklucza, nie wpuszcza.

Chrom **PR** (`ai:generated`, `ai:pr-opened`) zostaje na pull requescie.

## Mutex (fakt, nie etykieta)

```text
wolno brać  =  otwarte issue
            ∧  brak human stop (blocked / needs-feedback / park)
            ∧  brak żywego issue_to_pr na repo#n
            ∧  brak otwartego covering AI PR
            ∧  repo nie jest occupied (właśnie zmergowane / still-coding)
```

Źródła: receipt `~/.lokay/cycle/` + `gh pr list` + `merged_this_pass`.
`factory_begin` otwiera `pass_dir` i katalog z konfiguracji. Issues i PR-y listują żywo z GitHuba.
`refresh_occupancy` składa to po closeout jako higiena, nie jako bramka wyboru.

## Przejścia

```text
otwarte, bez decyzji  --triage-->  ready | blocked | needs-feedback | close | split
ready + brak mutexu   --dispatch-->  issue_to_pr   (ai:ready zostaje)
ready + otwarty AI PR --survey-->  skip implement  (ai:ready zostaje; closeout włada PR)
ready + occupied repo --select-->  skip implement  (health=waiting, nie stall)
PR zmergowany         --stage_clear + close-->  closed
konflikt PR           --close PR-->  ready zostaje, następny pass bierze od main
timeout + issue CLOSED --skip-->  issue_closed (nie continue, nie drugi PR)
```

Węzły Fali `stage_implementing` / `stage_pr_open` / `stage_repairing` zostają w DAG (kolejność), ale **nie nadają** `ai:in-progress` / `ai:pr-open` / `ai:ci-waiting` / `ai:repairing`. Plan to `ready` + zdjęcie resztek cache.

`localize` nie zamyka agenta w `tests/`: `test_foo.py` promuje `foo.py`,
a gdy produktu nadal brak — first-party importy z tych testów.
Trafienie w `skills/*.md` nie jest produktem — importy z testu i tak
otwierają `playbook.py`. Identyfikator `has_fair_hook` ze seeda szuka
w całym pliku, nie w pierwszych 8KiB.
Samodzielne `X` to stem platformy (twitter/tweet), nie zgubiony 1-znak.

`host_ff updated` w trakcie passa zatrzymuje `factory_begin` (`health=host_updated`):
git już nowy, import jeszcze stary — następny tick launchd przebudowuje koło.
Launchd nie robi `host_ff` gdy `mill.lock` jest trzymany (inaczej zjada
`updated=true`); `LOKAY_PROCESS_HEAD` i tak odmawia, gdy HEAD ruszył pod
żywym daemonem.

Pass katalogu (`factory_pass`):

```text
factory_begin (tani katalog / occupancy)
  → select / queue_conflict / implement (K=1; skip occupied; gdy selected)
    → health / receipt
  → survey PRs → inbox → ready → triage → konflikty  (gdy select.route == none)
    → closeout (najpierw merge otwartych PR)
      → reap resztek in-flight cache → ai:ready
        → refresh_occupancy (occupy live/merged; re-list leftover-ready only)
  → reap leftover worktrees gdy brak wybranego wiersza (KEEP live/occupancy / pr_survey_failed / open PR / dirty unpublished; one ls-remote per repo)
```

## Resztki (do zmiecenia)

Historyczne `ai:in-progress` / `ai:pr-open` / `ai:ci-waiting` / `ai:repairing` chowały pracę: inbox i ready ich nie brały, closeout nie miał PR. `reap_stale_implementing` zdejmuje je i wraca `ai:ready`. Mill ich więcej nie stawia.
