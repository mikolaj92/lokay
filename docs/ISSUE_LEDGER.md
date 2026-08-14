# Issue ledger — maszyna stanów

GitHub Issue jest księgą. Etykiety `ai:*` to **wyłączne** stany (jeden ledger stage na raz). Fala zmienia stan atomem `stage_label`. Agent nie ustawia etykiet.

## Stany

| Stan | Etykieta | Kto widzi | Co wolno |
| --- | --- | --- | --- |
| **undecided** | brak etykiety decyzyjnej | `list_inbox` | triage (nie implement) |
| **ready** | `ai:ready` | `list_ready` / `survey_ready` | `issue_to_pr` |
| **implementing** | `ai:in-progress` | nic w kolejce implement | żywy `issue_to_pr` albo wrótki |
| **pr-open** | `ai:pr-open` | closeout / PR-first | merge / repair; **nie** nowe `issue_to_pr` w tym repo |
| **ci-waiting** | `ai:ci-waiting` | closeout | czekać na checki (u nas zwykle wyłączone) |
| **repairing** | `ai:repairing` | `pr_repair` | jeden repair |
| **blocked** | `ai:blocked` | nikt | człowiek |
| **needs-feedback** | `ai:needs-feedback` | nikt | człowiek |
| **parked** | `frozen` / `ai:frozen` / `ai:tracker` | nikt | człowiek / rodzic splitu |
| **closed** | issue closed | nikt | koniec |

`ai:ready` jest **wynikiem triaży**, nie biletem wstępu. Wejście to otwarte, nierozstrzygnięte issue (inbox).

## Przejścia (Fala)

```text
otwarte, bez decyzji  --triage-->  ready | blocked | needs-feedback | close | split
ready                 --stage_implementing-->  implementing
implementing          --pr_create + stage_pr_open-->  pr-open
pr-open               --pr_merge + stage_clear + close-->  closed
pr-open               --pr_repair-->  repairing --> pr-open
implementing          --reap (brak żywego joba i brak PR)-->  ready
ready + otwarty AI PR --survey_ready-->  pr-open   (nie drugie issue_to_pr)
```

Pass katalogu (`factory_pass`):

```text
survey PRs → inbox → ready → triage → konflikty
  → closeout (najpierw merge otwartych PR)
    → reap porzuconego implementing
      → select / implement (max 4, 1 na repo)
```

## Limbo (bug, który ten dokument nazywa)

`stage_implementing` zdejmuje `ai:ready` **zanim** powstanie PR. Gdy `issue_to_pr` umrze (lease, timeout, czerwony test, push), issue zostaje na `ai:in-progress`. Inbox go nie bierze. Ready go nie bierze. Mill idzie dalej i widzi puste repo.

**Prawo:** `implementing` jest legalne tylko gdy (a) żyje proces `issue_to_pr` dla `repo#n`, albo (b) jest otwarty AI PR pokrywający `#n`. Inaczej `reap_stale_implementing` wraca issue na `ready`.
