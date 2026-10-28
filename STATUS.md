# STATUS.md

Aktualizacja: 2026-10-28 (koniec sesji).

- **`feat/detailed-search` → `origin`:** gotowe „Szukanie szczegółowe" — panel UI (wyklucz/wymagaj/fraza/w witrynie/poza witryną + język/czas/kategoria, chipy filtrów) oraz opcjonalne argumenty szczegółowe w MCP `web_search` i `POST /api/search` (`time_range`, `language`, `categories`, `exclude`, `include`, `phrase`, `site`, `not_site`). Bramka jakości w 100% zielona. Wypchnięte — czeka na PR i decyzję o deploju.
- **`feat/email-auth` → `origin`:** dokończona i zcommitowana autoryzacja e-mail przerwanej sesji (konta scrypt, sesje cookie, mailer SMTP, `request_guard`, testy poprawione). Wypchnięte — czeka na PR.
- Gałąź `release/1.0.0` scalona z `master` (PR #12); wersja `1.0.0` wydana.
- Strona `szukaj.dom` działa w sieci domowej (Pi-hole `*.dom` → serwer, Traefik → `127.0.0.1:8000`).
- Obowiązkowa kontrola przed commitem: `python3 scripts/check_project.py` (Ruff, tracked-files, backend, frontend, build, diff, staged-diff).
- Następne priorytety (rozwój ewolucyjny UX wyszukiwania, ustalone z Mariuszem):
  1. **Faza 2 (start następnej sesji):** silniki (`engines`), SafeSearch, „więcej wyników" (`pageno`), `before:`/`after:` — parametry już potwierdzone w kodzie SearXNG.
  2. Faza 3: tryb dwóch pól (temat + witryny → wybór stron → delegacja do AI; do uzgodnienia: OpenRouter/Gemini vs wirral-agents).
  3. Faza 4: notatnik w aplikacji (kopiuj-wklej).
- Nieprzydzielone pliki robocze w katalogu (poza Gitem): `.pi/`, `CLAUDE.md`, `project-checklist.md`.
