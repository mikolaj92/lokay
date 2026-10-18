## Cel

Usunąć nieaktualne zaprzeczenie istnienia wiersza COMPAT bez zmiany działających pinów. Dokumentacja ma opisywać konfigurację projektu, nie historię audytu.

Potwierdzone lokalnie: README, komentarze konfiguracji i istniejący test wymagają starego zastrzeżenia. `uv.lock` przypina app-factory do `65c7d82fc1d3bac8e238d89fc1f0096476ef9d5c`. W repozytorium nie ma źródłowego COMPAT.md; cytat ze zgłoszenia nie stanowi niezależnego potwierdzenia jego treści. Najmniejsza naprawa nie wymaga nowej deklaracji zgodności: wystarczy pozostawić prawdziwy opis przypiętych wersji.

## Pliki

1. `README.md`: w akapicie o pinach usunąć cały nawias od „tagi się resolvują” do starej trójki wersji. Zachować aktualne wersje oraz opis tagów, rewizji i `uv.lock`. Nie dodawać sekcji audytu ani historii zgłoszenia.
2. `pyproject.toml`: usunąć trzy nieaktualne komentarze bezpośrednio pod `[tool.uv.sources]`. Istniejące wpisy źródeł wystarczają; nie zastępować ich powtórzoną listą wersji.
3. `tests/test_dependency_pins.py`: zmienić istniejącą funkcję `test_docs_do_not_claim_missing_compat_v0611_row`, bez dodawania funkcji testowych. Nadać jej nazwę niezwiązaną z v0.6.11. Zastąpić wymagania starego zastrzeżenia sprawdzeniem jego nieobecności w README i komentarzach konfiguracji. Usunąć zakaz frazy „Platform BOM”, który nie sprawdza konfiguracji. W istniejących testach pinów i README uzupełnić brakujące sprawdzenie `my-usermanager` / `v0.5.11`.

Przed edycją ponownie przeczytać dotykany dokument i komentarze. Usuwać nieaktualną lub powtórzoną treść; liczba dodanych linii dokumentacji nie może przekroczyć liczby usuniętych. Bazowy zakres to trzy pliki. `uv.lock` i inne pliki zmieniać tylko wtedy, gdy wymaga tego przejście lokalnych kontroli; takie poprawki należą do zakresu i muszą pozostać.

## Testy

W zapisywalnym worktree, po wdrożeniu planu:

1. `uv run pytest tests/test_dependency_pins.py`.
2. `uv run pytest`.
3. `uv run ruff check .`.
4. `git diff --check`.
5. Przejrzeć diff: brak nowych funkcji testowych, brak starego zastrzeżenia w dokumentacji, bilans dodanych linii dokumentacji nie większy od usuniętych.

Wszystkie kontrole muszą przejść. Naprawić także wykryte blokady poza pierwotnym obszarem zgłoszenia, w tym rozbieżności pinów lub lockfile. Powtórzyć kontrole po poprawkach; nie cofać zmian potrzebnych do ich przejścia.

Podczas przygotowania planu nie uruchamiano kontroli ani nie zmieniano checkoutu tylko do odczytu. Wyszukiwanie ograniczono do bieżącego katalogu projektu.

## Poza zakresem

- Nowe funkcje produktu i przebudowa integracji auth lub runtime Fala.
- Prewencyjne aktualizacje zależności, których nie wymagają lokalne kontrole.
- Nowe funkcje testów jednostkowych, nowy mechanizm pobierania COMPAT i rozbudowa infrastruktury testowej.
- Ogólny audyt pozostałej dokumentacji i opisy historii zgłoszeń.
