# Issue ledger — decyzje, nie cache faktów

GitHub Issue jest księgą **decyzji**. Etykiety `ai:*` na issue to wyłącznie to, czego nie da się wyliczyć z GitHuba. Agent nie ustawia etykiet. In-flight (job, PR, checki) nie jest stanem issue.

## Stany (decyzje)

| Stan | Etykieta | Kto widzi | Co wolno |
| --- | --- | --- | --- |
| **undecided** | brak etykiety decyzyjnej | `list_inbox` | triage only — unlabeled is never `issue_to_pr` fuel; Label = start (`ai:ready` / `ready-for-agent`) |
| **ready** | `ai:ready` / `ready-for-agent` (ślad `work:ready` opcjonalny) | `list_ready` / leftover dual-ready | `issue_to_pr`, o ile brak human stop, żywego joba i covering open PR |
| **blocked** | `ai:blocked` | nikt | człowiek |
| **needs-feedback** | `ai:needs-feedback` | nikt | człowiek |
| **parked** | `frozen` / `ai:frozen` / `ai:tracker` | nikt | człowiek / rodzic splitu |
| **closed** | issue closed | nikt | koniec |

Otwarte issue **czeka na sito**. `ai:ready` / `ready-for-agent` **są biletem startu** (WORKING Label = start). `work:ready` jest śladem ledgeru po mark, nie substytutem unlabeled. Human stop (`ai:blocked` / `ai:needs-feedback` / park) wyklucza.

Chrom **PR** (`ai:generated`, `ai:pr-opened`) zostaje na pull requescie.

## Mutex (fakt, nie etykieta)

```text
wolno brać  =  otwarte issue z etykietą startu (`ai:ready` / `ready-for-agent`)
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
unlabeled             --select-->  none            (nie paliwo implement)
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
Launchd nie robi `host_ff` gdy `lokay.lock` jest trzymany (inaczej zjada
`updated=true`); `LOKAY_PROCESS_HEAD` i tak odmawia, gdy HEAD ruszył pod
żywym daemonem.

Pass katalogu (`factory_pass`), authored order:

```text
harvest_factory_children
  → host_ff
    → factory_begin_host_gate
      → begin: factory_begin
      → restart | blocked (host_behind): record_pass, bez produktu
    → pięć departmentów (self_repair, issue_triage, executor, pr_triage, pr_repair)
      → record_pass → factory_pass_terminal
    → reap_stale_worktrees (sibling z factory_begin_host_gate i factory_begin; nie bramkuje receipt)
```

`select_implement` jest zagnieżdżoną ścieżką egzekutora, nie pierwszym krokiem rodzica. Nie ma pętli „select.route == none → survey/closeout”.

## Resztki (do zmiecenia)

Historyczne `ai:in-progress` / `ai:pr-open` / `ai:ci-waiting` / `ai:repairing` chowały pracę: inbox i ready ich nie brały, closeout nie miał PR. `reap_stale_implementing` zdejmuje je i wraca `ai:ready`. Lokay ich więcej nie stawia.
