# HANDOFF.md — stan projektu

Aktualizacja: 2026-10-28.

## Stan bieżący: Szukanie szczegółowe gotowe lokalnie (`feat/detailed-search`)

- **Co powstało:** panel „Szukanie szczegółowe" w UI (`web/src/App.jsx`, `api.js`, `style.css`, ikona `sliders` w `Icon.jsx`) — pola Wyklucz/Muszą wystąpić/Dokładna fraza/W witrynie/Poza witrynie + selektory Język/Czas/Kategoria; aktywne filtry jako zdejmowalne chipy; `Escape` zamyka panel; „Nowe wyszukiwanie" czyści filtry.
- **Backend:** `mcp/server.py` — `build_detailed_query()` (skleja operatory `-"x"`, `+"x"`, `"fraza"`, `site:`, `-site:` z sanityzacją cudzysłowów), `sanitize_terms/sanitize_hosts`, `_searxng()` przyjmuje `time_range/language/categories`; `web_search` ma nowe opcjonalne argumenty (wstecznie zgodne, dokumentacja w `docs/MCP-USAGE.md`). `mcp/web_app.py` — `validated_advanced()` (ścisła walidacja, 400 przy błędach).
- **Testy:** `tests/test_detailed_search.py` (17 przypadków), 3 nowe testy Vitest; pełna bramka `python3 scripts/check_project.py` zielona (2026-10-28).
- **Niewypchnięte:** branch lokalny — push wymaga zgody Mariusza.
- **Równolegle:** `feat/email-auth` (commit `62dd09a`, lokalnie) — dokończona autoryzacja e-mail z przerwanej sesji; poprawione testy (logger `szukaj` nie propaguje do root; bramka wyłącza logi — patrz wzorzec `logging.disable` w `test_web_app.py`; login przy wyłączonej autoryzacji → 404). Też czeka na push/PR.

## Kontekst badania SearXNG (pod fazy 2–3)

- Parser SearXNG (`searx/query.py`) obsługuje w `q` tylko: `!silnik/kategoria`, `:język`, `!!bang`, `!!` (feeling lucky), `<limit` (timeout). Operatory `-/+/"..."/site:` idą verbatim do silników zewnętrznych.
- API `/search` przyjmuje dodatkowo: `categories`, `engines`, `language`, `time_range` (day/week/month/year), `safesearch` (0–2), `pageno` — do wykorzystania w fazie 2.

## Następny priorytet

1. Push + PR obu gałęzi po zgodzie Mariusza.
2. Faza 2 szczegółowego wyszukiwania: `engines`, `safesearch`, `pageno`, `before:`/`after:`.
3. Faza 3: tryb dwóch pól (temat + witryny) z delegacją do AI — Mariusz wskazał OpenRouter/Gemini lub wirral-agents; do uzgodnienia endpoint i klucz.
4. Faza 4: notatnik w aplikacji (kopiuj-wklej).

## Ustalenia i uwagi operacyjne

- GIT-FLOW w wersji z `feat/email-auth` mówi „Agent commituje sam" i wymaga trailer-a `Co-Authored-By`; commit auth podpisałem jako `GLM via opencode <noreply@z.ai>` (uczciwie — nie podszywam się pod Claude). Do decyzji Mariusza, jak podpisywać dalej.
- Sekrety: nie czytano `.env`; klucze SMTP/AUTH są env-owe.
- Brak dostępu do `docker.sock` z tej sesji (weryfikacja kontenerów niemożliwa).
