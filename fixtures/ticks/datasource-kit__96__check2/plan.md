## Cel

- Usunąć zależność od nieistniejącego API artefaktów bez regresji backendu wykonania, bezpieczeństwa routera ani stanu workerów.
- Najpierw sprawdzić stan docelowego worktree i jego diff. Ten checkout main nadal zawiera adapter i pin `v0.7.28`.
- Wyniki poprzednich prób traktować jako dowody historyczne, nie potwierdzenie aktualnego stanu ani zielonych kontroli.
- Zgłoszenie traktować wyłącznie jako dowód. Wyszukiwać tylko wewnątrz katalogu roboczego; nie czytać innych planów.
- Usunąć `FalaArtifactStore` zamiast tworzyć zamiennik. Zachować ogólny protokół `ArtifactStore` i leniwe importowanie opcjonalnych zależności.
- Zachować przekazanie callbacku, identyfikatorów, wejść i metadanych oraz niezmienione wyniki i wyjątki `FalaExecutionBackend`.
- Nie zmieniać odpowiedzialności za tworzenie runów, checkpointy, retry, journal ani procesy workerów.
- Wyeliminować źródło Git Fali zarówno z metadanych, jak i lockfile. Sam tag `v0.8.1` nadal uruchamiał zablokowany `git fetch`.
- Użyć archiwum HTTPS przypiętego do commita `27c179aee96daf6953ef36d6b1a007214d14a0db`, po potwierdzeniu budowania i publicznego API.
- Nie obchodzić ograniczeń sandboxa. Niedostępność archiwum zgłosić jako blokadę, bez powtarzania zablokowanego pobierania Git.
- Rozwiązać konflikt dokumentacji FastAPI przez usunięcie docstringa modułu i zachowanie potrzebnego opisu w README, bez odtwarzania docstringa.
- Nie dodawać komentarzy kodu, docstringów ani nowych testów jednostkowych.
- Każdy dotykany dokument przeczytać w całości przed zmianą. Usunąć treści nieaktualne i powtórzenia; dodane linie dokumentacji nie przekraczają usuniętych.
- Dokumentacja opisuje wyłącznie działanie projektu, bez historii zgłoszenia, uzasadnień procesu ani relacji z kontroli.

## Pliki

- `src/datasource_kit/adapters/fala.py`: usunąć adapter artefaktów, jego eksport, importy, protokoły i stałe używane tylko przez niego.
  Usunąć nieaktualny docstring modułu; nie zastępować go nowym. Zachować backend wykonania i jego obsługę błędów.
- `src/datasource_kit/adapters/fastapi.py`: przeczytać cały moduł, następnie usunąć wyłącznie jego początkowy docstring.
  Nie zmieniać routingu, zabezpieczeń, walidacji jednostek ani delegowania do control plane.
  Potrzebne informacje o działaniu przenieść zwięźle do README, eliminując nieaktualne porównanie z adapterem artefaktów.
- `tests/adapters/test_fala_artifact_store.py`: usunąć testy oparte na fikcyjnym `fala.artifacts` wraz z plikiem.
- `tests/adapters/test_fala_extra_source.py`: dostosować istniejące asercje do dokładnego URL archiwum i braku nadpisania źródłem Git.
  Nie dodawać funkcji testowych ani nowych przypadków jednostkowych.
- `pyproject.toml`: ustawić bezpośrednią zależność archiwalną Fali i usunąć `tool.uv.sources.fala` oraz nieaktualne komentarze integracji.
  Zachować niezależność rdzenia i pozostałych extras.
- `uv.lock`: wygenerować przez uv; sprawdzić zgodność URL, wersji i sumy integralności archiwum z metadanymi.
  Nie cofać zmian przypiętych wersji potrzebnych do przejścia lokalnych kontroli.
- `README.md`: skrócić sekcje Execution Backend i Install, usuwając obietnicę adaptera artefaktów oraz opis starego tagu Git.
  Opisać rzeczywiste źródło Fali i wykonanie przez `record_in_process`.
  Zachować zwięzły opis FastAPI: opcjonalna instalacja, leniwy import, montowanie routera oraz zabezpieczenia należące do hosta.
  Zachować informację, że router deleguje do control plane i sam nie uruchamia ani nie zatrzymuje procesów.
  Połączyć przenoszone informacje z istniejącym opisem extras; nie powielać opisów i nie zwiększać bilansu linii dokumentacji.
- Pozostałe pliki wskazane przez rzeczywiste niepowodzenia lokalnych kontroli: minimalne poprawki pozostają w zakresie, także uzgodnienie wersji.
  Przed edycją odczytać plik; dla dokumentów zachować powyższy bilans linii. Nie cofać koniecznych poprawek dla zmniejszenia diffu.

## Testy

- W docelowym worktree odczytać konfigurację kontroli. Obecne CI uruchamia `uv run --group dev pytest -q` na Pythonie 3.12 i 3.13.
- Uruchomić `uv lock --check`, następnie `uv sync --frozen --all-extras` na Pythonie 3.14.3 użytym przez setup.
- Powtórzyć instalację z pustym cache uv umieszczonym wewnątrz worktree. Potwierdzić pobieranie archiwum, a nie uruchomienie Git.
- Sprawdzić też `uv sync --locked --all-extras`, ponieważ ostatni przedstawiony przebieg używał tego wariantu.
- Uruchomić istniejącą pełną suite przez `uv run --extra dev pytest` oraz polecenie CI na Pythonie 3.12 i 3.13.
- Zachować istniejące testy backendu wykonania i routera. Chronią przekazanie callbacku, wyjątków, granice control plane i błędy nieznanych jednostek.
- Na rzeczywiście zainstalowanej Fali sprawdzić wersję, publiczny import i sygnaturę `record_in_process`, bez podstawiania modułów.
- W tymczasowej bazie wewnątrz worktree utworzyć run zgodnie z rzeczywistym API i wykonać callback przez backend.
  Potwierdzić jednokrotne wywołanie, tożsamość wyniku i propagację wyjątku; nie dotykać baz ani stanu konsumentów.
- Brak środowiska wymaganego przez rzeczywistą Falę zgłosić jako blokadę integracji, nie jako sukces.
- Wyszukać pozostałości `FalaArtifactStore`, `fala.artifacts` i starego źródła Git wyłącznie wewnątrz worktree.
- Sprawdzić `git diff --check`, brak dodanych komentarzy i docstringów, brak nowych testów jednostkowych oraz bilans dokumentacji.
- Usunąć wyłącznie własne tymczasowe dane weryfikacji. Nie usuwać zastanego stanu worktree ani potrzebnych zmian.
- Naprawić wszystkie rzeczywiste niepowodzenia lokalnych kontroli i powtórzyć kontrole po ostatniej zmianie.
- Nie uznawać historycznego wyniku 316 testów ani zielonego CI za wynik końcowych zmian.
- Weryfikację PR i push wykonuje lokay, nie wykonawca zmian. Nie publikować gałęzi ani nie czekać na CI zamiast kontroli lokalnych.

## Poza zakresem

- Własny magazyn artefaktów, adapter pozorujący brakujące API oraz implementacja magazynu po stronie Fali.
- Niezależne refaktoryzacje runtime, fleet i journal, które nie są wymagane przez lokalne kontrole.
- Rozbudowa dokumentacji, komentarze kodu, docstringi i nowe testy jednostkowe.
- Wyszukiwanie poza katalogiem roboczym, czytanie innych planów i artefaktów syntezy oraz obchodzenie ograniczeń sandboxa.
- Samodzielne wypychanie zmian i weryfikacja PR zamiast lokay.
