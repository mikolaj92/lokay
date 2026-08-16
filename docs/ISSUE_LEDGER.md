# Issue ledger — decyzje, nie cache faktów

GitHub Issue jest księgą **decyzji**. Etykiety `ai:*` na issue to wyłącznie to, czego nie da się wyliczyć z GitHuba. Agent nie ustawia etykiet. In-flight (job, PR, checki) nie jest stanem issue.

## Stany (decyzje)

| Stan | Etykieta | Kto widzi | Co wolno |
| --- | --- | --- | --- |
| **undecided** | brak etykiety decyzyjnej | `list_inbox` | triage (nie implement) |
| **ready** | `ai:ready` | `list_ready` / `survey_ready` | `issue_to_pr`, o ile brak żywego joba i brak covering open PR |
| **blocked** | `ai:blocked` | nikt | człowiek |
| **needs-feedback** | `ai:needs-feedback` | nikt | człowiek |
| **parked** | `frozen` / `ai:frozen` / `ai:tracker` | nikt | człowiek / rodzic splitu |
| **closed** | issue closed | nikt | koniec |

`ai:ready` jest **wynikiem triaży**, nie biletem wstępu. Wejście to otwarte, nierozstrzygnięte issue (inbox). Zostaje na issue przez cały bieg, aż merge + `stage_clear` + close.

Chrom **PR** (`ai:generated`, `ai:pr-opened`) zostaje na pull requescie.

## Mutex (fakt, nie etykieta)

```text
wolno brać  =  ai:ready
            ∧  brak żywego issue_to_pr na repo#n
            ∧  brak otwartego covering AI PR
            ∧  repo nie jest occupied (właśnie zmergowane / still-coding)
```

Źródła: receipt `~/.lokay/cycle/` + `gh pr list` + `merged_this_pass`.
`refresh_occupancy` składa to po closeout; `select_implement` tylko czyta.

## Przejścia

```text
otwarte, bez decyzji  --triage-->  ready | blocked | needs-feedback | close | split
ready + brak mutexu   --dispatch-->  issue_to_pr   (ai:ready zostaje)
ready + otwarty AI PR --survey-->  skip implement  (ai:ready zostaje; closeout włada PR)
PR zmergowany         --stage_clear + close-->  closed
konflikt PR           --close PR-->  ready zostaje, następny pass bierze od main
```

Węzły Fali `stage_implementing` / `stage_pr_open` / `stage_repairing` zostają w DAG (kolejność), ale **nie nadają** `ai:in-progress` / `ai:pr-open` / `ai:ci-waiting` / `ai:repairing`. Plan to `ready` + zdjęcie resztek cache.

Pass katalogu (`factory_pass`):

```text
survey PRs → inbox → ready → triage → konflikty
  → closeout (najpierw merge otwartych PR)
    → reap resztek in-flight cache → ai:ready
      → refresh_occupancy (re-list PRs ∪ live i2pr ∪ just-merged)
        → reap leftover worktrees (KEEP live / open PR / dirty unpublished)
          → select / implement (K=1; skip occupied)
```

## Resztki (do zmiecenia)

Historyczne `ai:in-progress` / `ai:pr-open` / `ai:ci-waiting` / `ai:repairing` chowały pracę: inbox i ready ich nie brały, closeout nie miał PR. `reap_stale_implementing` zdejmuje je i wraca `ai:ready`. Mill ich więcej nie stawia.
