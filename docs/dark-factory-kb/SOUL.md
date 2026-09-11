# Dusza klepacza (soul)

Źródło: Mikołaj, 2026-09-11 — potwierdzone słowo w słowo z Lokayem przed zapisem.
Status: **kanon intencji produktu**. Nie L5 dark factory. Nie „wyrzuć człowieka”.

## Po co to jest

Cel nie jest wyeliminować człowieka. Cel jest odwrotny: zdjąć pośrednie, wyczerpujące klepanie (kolokwia, które da się zautomatyzować), żeby energia szła w to, w czym człowiek jest dobry — myślenie o taskach, architektura, trudne decyzje, niewygodne pytania QA.

Automatyzujemy to, co wyczerpuje bez wartości. Człowiek zostaje tam, gdzie jest wartość.

## Dwie ciężkie rzeczy (lokal / proces)

### 1. Graf całego procesu

Klepacz czy deweloper — bez różnicy. „Usługa mięsa” i „usługa AI” to ta sama rola w łańcuchu: muszą zrobić pewne rzeczy.

Większość tych rzeczy jest **deterministyczna**:

1. Wejdź do miejsca zarządzania projektem
2. Odczytaj następną robotę
3. Przetwórz ticket w kontekście
4. Zacznij implementację *(tu wkracza ciężar nr 2)*
5. Branch
6. Commit(y) — część implementacji to kolejne commity
7. Push na remote (origin)
8. Otwórz pull request
9. Review *(ciężar nr 3 / osobna rola)*
10. Merge albo poprawki (poprawki prawie zawsze bywają)

To ma żyć w **grafie i podgrafach** — nie w jednym ogromnym węźle. Gdzie temat ma dużo małych akcji → podgraf.

### 2. Implementacja (wysoka entropia)

Tu wchodzi agent (albo człowiek): *jak najlepiej zaimplementować*. To nie jest skrypt „weź następny”.

Lekkie, wąskie agenty są OK, np.:

- agent tylko planuje, jak zrobić ten issue
- agent tylko rozpisuje pliki / taski

Nie jeden gruby mózg orkiestrujący tool-callingiem.

### 3. Review (osobna rola)

Po PR wkracza krytyczny przegląd: spójność projektu, architektura (chyba że PR właśnie ją zmienia), komentarze. Potem merge albo poprawki.

QA (strategia) zostaje: periodycznie sprawdza, czy projekt działa, zadaje niewygodne pytania („czemu tak — nie da się prościej?”). Dobry inżynier QA nie znika — zyskuje czas.

## Deterministyczne vs agentowe

| DET (skrypt / atom) | Agent (structured output) |
|---------------------|---------------------------|
| lista / pick issue | plan jak zrobić issue |
| branch, commit, push | implementacja |
| open PR | krytyczny review |
| merge policy | rozpisanie plików/tasków gdy trzeba |

## Kryterium sukcesu (ludzkie)

Człowiek ma energię na architekturę i niewygodne pytania — bo nie spalił dnia na: „weź ticket → branch → push → otwórz PR → dogadaj merge”.

Technicznie: zmergowane `ai/fix` na tipie hosta w sensownym oknie czasu — nie ładny JSON bez skutku.

## Czym to NIE jest

- Nie lights-out bank (L5)
- Nie „agent wybiera sobie pracę z czatu”
- Nie jeden monolityczny graf wszystkiego
- Nie zastąpienie inżyniera, PO, UX ani QA-strategii

## Powiązane

- `KLEPACZ.md` — kanon nazwy i ram (ready-for-agent, Merge Off|Classify|Always)
- `WORKING_KLEPACZ_GRAPH.md` — cienki design wdrożeniowy
- `graph-variants/` — wiele wersji grafu/podgrafów (eksploracja → potem składanie)

## Prawo nazwy (CEO 2026-09-11)

Nie ma **milla / młyna** jako nazwy własnej. To jest **Lokaj** (butler) — pomaga, klepie ticket→PR. „Mill” to było potknięcie językowe; w docs i mowie mówimy **Lokaj / lokaj**. (Obcy research może nadal pisać „coding mill” o cudzych systemach — to nie nasza marka.)
