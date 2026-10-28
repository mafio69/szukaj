# STATUS.md

Aktualizacja: 2026-10-28.

- **`feat/detailed-search` (lokalnie):** gotowe „Szukanie szczegółowe" — panel UI (wyklucz/wymagaj/fraza/w witrynie/poza witryną + język/czas/kategoria, chipy filtrów) oraz opcjonalne argumenty szczegółowe w MCP `web_search` i `POST /api/search` (`time_range`, `language`, `categories`, `exclude`, `include`, `phrase`, `site`, `not_site`); pełna bramka jakości zielona. Czeka na commit/push i PR do `develop`/`master` po decyzji Mariusza.
- **`feat/email-auth` (lokalnie, commit `62dd09a`):** dokończona i zcommitowana autoryzacja e-mail poprzedniej sesji (konta scrypt, sesje, mailer SMTP, `request_guard`, testy naprawione). Niewypchnięta — wymaga decyzji o PR.
- Gałąź `release/1.0.0` scalona z `master` (PR #12); wersja `1.0.0` wydana.
- Strona `szukaj.dom` działa w sieci domowej (Pi-hole `*.dom` → serwer, Traefik → `127.0.0.1:8000`).
- Obowiązkowa kontrola przed commitem: `python3 scripts/check_project.py` (Ruff, tracked-files, backend, frontend, build, diff, staged-diff).
- Następne priorytety (ustalone z Mariuszem, rozwój ewolucyjny UX wyszukiwania):
  1. Faza 2: silniki (`engines`), SafeSearch, „więcej wyników" (`pageno`), `before:`/`after:`.
  2. Faza 3: tryb dwóch pól (temat + witryny → wybór stron → delegacja do AI; kandydaci: OpenRouter/Gemini lub wirral-agents).
  3. Faza 4: notatnik w aplikacji (kopiuj-wklej) — pomysł Mariusza.
- Nieprzydzielone pliki robocze w katalogu (poza Gitem): `.pi/`, `CLAUDE.md`, `project-checklist.md`.
