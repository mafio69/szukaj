# HANDOFF.md — stan projektu

Aktualizacja: 2026-10-28 (pałeczka na najbliższą sesję).

## Start dnia: Faza 2 szczegółowego wyszukiwania

Gałąź: nowa z `origin/develop` (po scaleniu otwartych PR — najpierw dopytaj Mariusza o stan PR i deploju).

**Zakres fazy 2:** parametry API SearXNG potwierdzone w źródłach (`searx/webadapter.py`):
- `engines` — lista silników po przecinku (np. `google,bing,duckduckgo,wikipedia`); webapp filtruje nieznane nazwy.
- `safesearch` — `0/1/2` (wyłączony/umiarkowany/ściśle).
- `pageno` — strona wyników („więcej wyników" pod listą).
- `before:`/`after:` — operatory dat przekazywane silnikom (jak `site:` — doklejane do `q`, patrz `build_detailed_query` w `mcp/server.py`).

**Miejsca zmian (wzorce z fazy 1):** `mcp/server.py` (stała `ENGINES`/walidacja + param w `_searxng` i `web_search`), `mcp/web_app.py` (`validated_advanced`), `web/src/App.jsx` + `api.js` (nowe pola/chipy), testy: `tests/test_detailed_search.py`, `web/src/App.test.jsx`. Listę silników można pobrać z instancji SearXNG (`/config` zwraca JSON) albo začíst na stałe — uzgodnić z Mariuszem.

## Stan repo (koniec sesji 2026-10-28)

- `feat/detailed-search` **wypchnięta** do origin: panel UI + argumenty szczegółowe MCP/API (commit `143d140` + docs). Czeka na PR.
- `feat/email-auth` **wypchnięta** do origin: dokończona autoryzacja e-mail (commit `62dd09a`). Czeka na PR.
- Bramka `python3 scripts/check_project.py` zielona na obu gałęziach.
- Deploy planowany przez Mariusza po PR.

## Ustalenia i pułapki

- Logger `szukaj` ma `propagate=False`, a bramka testowa wyłącza logi globalnie (`logging.disable(CRITICAL)` w `scripts/check_project.py`) — testy logów muszą wzorować się na `tests/test_web_app.py` (`logging.disable(logging.NOTSET)` + `addCleanup`).
- Commity podpisuję `Co-Authored-By: GLM via opencode <noreply@z.ai>` (GIT-FLOW z gałęzi auth wymaga trailer-a „Claude Opus 5.5" — nie podszywam się; kwestia otwarta u Mariusza).
- Faza 3 (AI: OpenRouter/Gemini vs wirral-agents) i faza 4 (notatnik) — dopiero po fazie 2 i po decyzji Mariusza o endpointcie AI.
- Nie czytać `.env`; brak dostępu do `docker.sock` z sesji agenta.
