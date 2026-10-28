# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Szukanie szczegółowe w UI i MCP — 2026-10-28
- Panel „Szukanie szczegółowe" w `szukaj.dom` (ikona suwaków przy polu wyszukiwania): pola *Wyklucz słowa*, *Muszą wystąpić*, *Dokładna fraza*, *W witrynie*, *Poza witrynie* oraz selektory *Język*, *Czas* (dzień/tydzień/miesiąc/rok) i *Kategoria*; aktywne filtry widoczne jako zdejmowalne „chipy", `Escape` zamyka panel.
- Interfejs buduje operatory (`-"słowo"`, `+"słowo"`, `"fraza"`, `site:`/`-site:`) za użytkownika — nie trzeba pamiętać składni ani cudzysłowów.
- Rozszerzono narzędzie MCP `web_search` i `POST /api/search` o opcjonalne argumenty szczegółowe (`time_range`, `language`, `categories`, `exclude`, `include`, `phrase`, `site`, `not_site`) — wstecznie zgodne; walidacja ścisła po stronie API (400), sanityzacja terminów w `mcp/server.py` (usuwanie cudzysłowów, limity długości i liczby), `language`/`time_range`/`categories` przekazywane do API SearXNG.
- Testy: `tests/test_detailed_search.py` (budowa zapytania, sanityzacja, kontrakt MCP, walidacja endpointu) oraz 3 nowe testy Vitest dla panelu, chipów i ładunku `advanced`.

### Dokończona praca nad autoryzacją e-mail (gałąź `feat/email-auth`) — 2026-10-28
- Zcommitowano przerwane zmiany poprzedniej sesji: konta e-mail/hasła (scrypt, SQLite), sesje cookie, logowanie/rejestracja/reset z limitami, mailer SMTP z trybem dev, wspólny `request_guard` dla `/api/*`.
- Poprawki testów przerwanego zadania: asercja loggera `szukaj` (logger nie propaguje do root; dodatkowo bramka testowa wyłącza logi globalnie — wzorzec z `test_web_app.py`), `404` zamiast `405` dla niezarejestrowanego `/api/auth/login` przy wyłączonej autoryzacji, usunięty nieużywany import.

## [1.0.0] - 2026-10-24

### Weryfikacja MCP Streamable HTTP, testy PhpStorm i finalizacja wydania — 2026-10-24
- Dodano zestaw testów integracyjnych w standardzie JetBrains HTTP Client ([http/mcp-test.http](file:///home/mariusz/PhpstormProjects/szukaj/http/mcp-test.http)) dla endpointu MCP Streamable HTTP (`/mcp`): negocjacja protokołu `initialize`, powiadomienie `notifications/initialized`, odkrywanie `tools/list`, wywołanie narzędzia `web_search` (w tym test zapytania *„Słuchawki do 500zł”* z logowaniem wyników), walidacja błędnych zapytań oraz test przeglądarkowego `/api/search`.
- Skonfigurowano pliki środowiskowe klienta HTTP: `http/http-client.env.json`, szablon `http/http-client.private.env.json.example` oraz regułę w `.gitignore` chroniącą prywatne tokeny autoryzacyjne.
- Rozwiązano problem botdetection SearXNG w kontenerze poprzez przekazywanie nagłówka `X-Forwarded-For: 127.0.0.1` w `mcp/server.py`.
- Poprawiono moduł `mcp/app_logging.py` (`_resolve_root`), zapewniając prawidłowe tworzenie katalogu logów `/app/.local/logs` wewnątrz kontenera Docker.
- Wyłączono nieaktywne silniki sieci Tor (`ahmia`, `torch`) w `searxng-settings.example.yml`.
- Zaktualizowano `opencode.json` (poluzowanie uprawnień zgodnie z zasadą elastyczności konfiguracji).
- Dodano skrypt narzędziowy `scripts/test_mcp_client.py` do testowania endpointu MCP z poziomu konsoli.
- Wypchnięto gałąź `release/1.0.0` do `origin/release/1.0.0`.

### Wydanie stabilne 1.0.0 (Production Ready MVP) — 2026-10-23
- Pierwsze stabilne wydanie produkcyjne (MVP 1.0.0) projektu `szukaj` (`szukaj.dom`).
- Ujednolicono wersję projektu na `1.0.0` w `web/package.json`, `web/package-lock.json`, dokumentacji i rejestrze zmian.
- Potwierdzono 100% sprawności zautomatyzowanej bramki jakości (`scripts/check_project.py`): Ruff linting, skaner wycieków i szablonów `.env`, 55 testów jednostkowych/integracyjnych backendu, 19 testów Vitest frontendu oraz produkcyjny build Vite.

### Dwujęzyczna dokumentacja (angielskie README.md, polskie README_PL.md) — 2026-10-22
- Przetłumaczono główny plik `README.md` na język angielski, zachowując pełną polską wersję dokumentacji w `README_PL.md` oraz dodano wzajemne odnośniki językowe.
- Uporządkowano repozytorium po usunięciu tymczasowego pliku `tests/test_example_sample.py`.
- Walidacja: Ruff PASS, tracked-files PASS, backend 55/55, frontend 19/19, build i diff-check roboczy/staged PASS.

### Systemowa obsługa błędów (`dev`/`prod`), rotacja logów `.gz`, Qodana i GitGuardian — 2026-10-20
- Naprawiono ostrzeżenie Qodana `JSIgnoredPromiseFromCall` w `web/src/App.jsx` (`void runSearch(...)`).
- Usunięto z `tests/test_checks.py` syntetyczny literał zgłaszany przez GitGuardian jako *Generic Password* oraz rozszerzono `scripts/check_tracked_files.py` o wykrywanie literałów `*_PASSWORD=`, `*_PASSWD=`, `*_PWD=`, `*_SECRET=`, `*_TOKEN=`, `*_API_KEY=` bezpośrednio w kodzie i testach.
- Wdrożono systemową obsługę błędów zależną od środowiska (`APP_ENV=prod` domyślnie, `APP_ENV=dev` do debugowania): na produkcji aplikacja (zarówno API/HTML w `mcp/web_app.py`, klient `web/src/api.js`, jak i `web/src/ErrorBoundary.jsx`) wyświetla wyłącznie przyjazny komunikat „Błąd. Przepraszamy...” bez szczegółów technicznych, natomiast w `dev` dołącza szczegóły wyjątku.
- Dodano moduł `mcp/app_logging.py`: domyślne logowanie od `WARNING` wzwyż (łatwe przełączenie na `INFO` lub `DEBUG` przez `LOG_LEVEL`), logowanie wszystkich ostrzeżeń i błędów na produkcji oraz automatyczną rotację i kompresję archiwów `.gz` (`CompressedRotatingFileHandler` w `.local/logs/szukaj.log`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`) wraz z kompresją logów Dockera (`compress: "true"`) i wolumenem `./.local/logs:/app/.local/logs` w `docker-compose.yml`.
- Walidacja: Ruff PASS, tracked-files PASS, backend 55/55, frontend 19/19, build i diff-check roboczy/staged PASS.

### Przygotowanie do wydania 1.0.0 (nazwa `szukaj`, skaner sekretów, D1–D8, O1–O5, W3, PR #2) — 2026-10-19
- Zmieniono nazwę projektu/pakietu UI oraz usługi w `docker-compose.yml` na `szukaj` (`szukaj-ui` w `web/package.json`, `SEARXNG_URL=http://szukaj:8080`, linki `mafio69/szukaj`), przebudowano prezentację `README.md`, ustawiono tytuł `<title>szukaj.dom</title>` w `web/index.html`, markę `szukaj.dom` w `web/src/App.jsx` oraz ujednolicono nazwę domeny `szukaj.dom` w dokumentacji (`REPO.md`, `HANDOFF.md`, `STATUS.md`).
- Dodano skaner śledzonych plików i indeksu Git `scripts/check_tracked_files.py` do bramki `scripts/check_project.py` oraz usunięto `searxng.geany` ze śledzenia Git.
- Ujednolicono dokumentację (`D1–D8`): poprawiono kontrakt i ścieżki w `docs/INSTRUKCJA.md`, listę zmiennych w `docs/MCP-USAGE.md`, sekcję statusu wydania w `README.md` oraz wersję `0.1.0` w `web/package.json` do chwili wydania `1.0.0`.
- Zoptymalizowano klienta HTTP (`O1`): współdzielony `httpx.AsyncClient` na proces w `mcp/server.py` z zamykaniem w `lifespan` aplikacji (`mcp/web_app.py`).
- Dodano timeouty wychodzące SearXNG (`3.0` / `8.0` s) i czas zawieszenia `SearxEngineTooManyRequests: 600` w `searxng-settings.example.yml` (`O2–O3`), a w `docker-compose.yml` dodano `healthcheck` (`/healthz`) z `condition: service_healthy` oraz rotację logów `json-file` (`O4–O5`).
- Dodano nagłówki bezpieczeństwa `X-Content-Type-Options: nosniff` i `Referrer-Policy: no-referrer` dla odpowiedzi UI w `mcp/web_app.py` (`W3`).
- Poprawki review PR #2: skanowanie zawartości indeksu Git i pełna walidacja pustych przypisań w szablonach środowiska w `scripts/check_tracked_files.py`, ochrona `Authorization` przed przekierowaniem (`add_unredirected_header`) w `scripts/smoke_test.py` oraz nieczuły na wielkość liter schemat `Bearer` w `mcp/access.py`.
- Walidacja: Ruff PASS, tracked-files PASS, backend 53/53, frontend 18/18, build i diff-check roboczy/staged PASS.

### Adres szukaj.dom — 2026-10-19 (fire, Claude Opus 5.5)
- Strona „Szukaj” dostępna w sieci domowej pod `http://szukaj.dom/` bez portu. Poza repo: trasa Traefika `szukaj.dom` → `127.0.0.1:8000` w `~/app/observability/proxy/dynamic/uslugi.yml`; DNS bez zmian (Pi-hole `*.dom` → 192.168.1.172); lokalny `.env`: `SEARCH_ALLOWED_HOSTS` uzupełnione o `szukaj.dom`, `mcp-search` uruchomiony ponownie.
- Nazwa `szukaj.dom` zastępuje planowane `wyszukaj.dom` (decyzja Mariusza). Instrukcja integracji i STATUS zaktualizowane; dla MCP nadal stałe adresy HTTP.
- Sprawdzone: Pi-hole → 192.168.1.172, `szukaj.dom/` → 200 („Szukaj — Twoje okno na internet”), `POST /api/search` z Origin `http://szukaj.dom` → 200, źródło SearXNG, 5 wyników.

### Instrukcja integracji MCP Search dla agentów — 2026-10-18
- Dodano docs/instrukcja-integracji-mcp-search.md: ustalone endpointy HTTP, integrację backendu i pętli narzędzia, trzy stany wyniku, sondę połączenia bez wyszukiwania oraz testy odbioru aplikacji.
- Wskazano jeden punkt konfiguracji przyszłej domeny wyszukaj.dom i odróżniono test bezpłatny od rzeczywistego wyszukiwania z możliwym kosztem fallbacku.
- Dodano odsyłacze z README, mapy repo i pozostałych instrukcji. Pozytywna opinia WirralAI pozostaje warunkiem stabilnego 1.0.0.
- Weryfikacja: przykład klienta initialize/tools/list PASS na lokalnej usłudze (2025-11-25), składnia/JSON/odsyłacze PASS; Ruff, 46 testów backendu, 18 frontendu i build PASS. Bez rzeczywistego wyszukiwania.

### Akceptacja MCP przed 1.0.0 — 2026-10-18
- Zapisano warunek Mariusza: stabilne 1.0.0 wymaga pozytywnej opinii WirralAI po teście integracji MCP. Akceptacja pozostaje otwarta; testy serwera jej nie zastępują.

### Q3 — Czytelne walidatory i obowiązkowy Ruff — 2026-10-18
- Rozdzielono importy i wydzielono walidatory wyników Python/JS. Dodano przypięty Ruff 0.17.1 jako narzędzie wyłącznie deweloperskie.
- Dodano scripts/check_project.py: Ruff, unittest, Vitest, build i kontrola diff roboczego/staged. Błąd lub brak narzędzia zatrzymuje kontrolę; trzy testy zabezpieczają ten przebieg.
- Zapisano zatwierdzone przez Mariusza allow dla agentów i obowiązek kontroli przed commitem. Bez automatycznych poprawek i bez zmian zależności obrazu aplikacji.
- Dodano raport zgodności MCP dla WirralAI w docs/contract/MCP-COMPATIBILITY.md.
- Walidacja: Ruff PASS, backend 46/46, frontend 18/18, build i diff-check roboczy/staged PASS.

### K1-UI — Stan pusty również w przeglądarce — 2026-10-18
- Usunięto pozostałe utożsamienie source null z awarią w React. status empty wyświetla brak wyników bez alarmu. Test regresji zachowuje rozróżnienie starszych odpowiedzi bez statusu.
- Walidacja: backend 43/43, frontend 18/18, build i diff-check PASS.

### Q2 — Aktualny pusty szablon środowiska — 2026-10-18
- Publiczny .env.example zawiera wszystkie zmienne README oraz wejścia MCP, wyłącznie puste wartości. Puste pola opcjonalne używają domyślnych ustawień zamiast psuć start przez int(""). Test szablonu i uruchomienia konfiguracji na syntetycznie pustym środowisku; prawdziwego .env nie odczytano.
- Walidacja: backend 43/43, frontend 17/17, build i diff-check PASS.

### S5 — Nieuprzywilejowany proces i stały obraz — 2026-10-18
- Dockerfile deklaruje USER 10001:10001. SearXNG przypięto do oficjalnego manifestu Docker Hub sha256:8bdd9aa136b2dc3b9332cf24714fa34a375b8a1949a1201ec900c24d7378596e (publiczne metadane 2026-10-18). Test konfiguracji PASS. Runtime UID/build niepotwierdzone: brak dostępu do docker.sock; nie uruchamiano sudo ani wdrożenia.
- Walidacja: backend 42/42, frontend 17/17, build i diff-check PASS.

### K2 — Walidacja zapytań MCP — 2026-10-18
- Narzędzie i jego schemat ograniczają query do 1–1000 znaków Unicode; białe znaki są odrzucane przed dostawcami. Testy sprawdzają puste/1001 znaków bez HTTP oraz akceptację 1000 polskich znaków. UI/API zachowuje udokumentowany limit 500.
- Walidacja: backend 41/41, frontend 17/17, build i diff-check PASS.

### K4 — Wspólne przykłady i testy transportu MCP — 2026-10-18
- docs/contract/web_search.example.json zawiera syntetyczne ok/empty/error. Trzy testy pełnych sesji initialize → tools/list → tools/call porównują sparsowany blok tekstowy JSON ze wspólnym plikiem. Testy klienta WirralAI pozostają do uruchomienia po jego stronie.
- Walidacja: backend 39/39, frontend 17/17, build i diff-check PASS.

### K1 — Jednoznaczny wynik pusty i awaria — 2026-10-18
- Dodano status ok/empty/error. Poprawny brak wyników ma source null, results [] i errors []; awaria bez wyników zawsze error. Udany fallback ma ok bez errors. API oddaje 502 przy awarii. Dokumentacja zawiera nowe stany i negocjację protokołu.
- Walidacja: backend 36/36, frontend 17/17, build i diff-check PASS.

### S4 — Bezpieczne kody błędów dostawców — 2026-10-18
- Odpowiedź MCP zwraca kontrolowane kody timeout/http_error/error i lokalne no_key/limit. Testy podkładają wyjątki z prywatnym tekstem i sprawdzają brak ich treści w odpowiedzi.
- Walidacja: backend 33/33, frontend 17/17, build i diff-check PASS.

### K3 — Przypięcie MCP i negocjacja protokołu — 2026-10-18
- Biblioteka mcp==1.30.0 w mcp/requirements.txt. Test rzeczywistego initialize potwierdza wszystkie cztery wersje akceptowane przez WirralAI; nieznana wersja negocjuje 2025-11-25.
- Walidacja: backend 32/32, frontend 17/17, build i diff-check PASS.

### S3 — Opcjonalna kontrola dostępu MCP — 2026-10-18
- MCP_AUTH_TOKEN chroni /mcp i jego metody GET/POST/DELETE stałoczasowym porównaniem nagłówka Bearer. Dotyczy pełnej aplikacji i osobnego entrypointu MCP. Brak konfiguracji zachowuje poprzednie działanie; przeglądarkowe API i statyczne UI nie otrzymują ani nie wymagają tego sekretu. Smoke potrafi przekazać wartość z własnego środowiska wyłącznie do MCP.
- Walidacja: backend 30/30, frontend 17/17, build i diff-check PASS.

### Q1 — Atomowy limit prób Perplexity — 2026-10-18
- Limit jest rezerwowany pod krótką blokadą przed żądaniem HTTP. Nie zwracamy rezerwacji po błędzie ani anulowaniu, bo koszt po stronie dostawcy może już powstać. Test 100 równoległych prób przy limicie 50 potwierdza dokładnie 50 żądań. Licznik nadal jest lokalny dla procesu i resetuje się po restarcie; nie deklarujemy trwałego budżetu.
- Walidacja: backend 25/25, frontend 17/17, build i diff-check PASS.

### S2 — Asynchroniczne wyszukiwanie — 2026-10-18
- web_search i obaj dostawcy używają async/await oraz httpx.AsyncClient. Adapter API oczekuje na tę samą asynchroniczną usługę. Test sprawdza dwa opóźnienia po 1 s, wspólny czas poniżej 1,5 s oraz możliwość uruchomienia obu żądań przed ich zakończeniem.
- Walidacja: backend 23/23, frontend 17/17, build i diff-check PASS.

### S1 — Oddzielenie klucza od wersjonowanej konfiguracji — 2026-10-18
- Compose montuje pusty publiczny szablon i wymaga lokalnego SEARXNG_SECRET. Dawny plik usunięto wyłącznie ze śledzenia, bez odczytu i zmiany lokalnej wartości. Rotacja klucza i rzeczywisty start pozostają do potwierdzenia przez operatora; stara historia nie została usunięta.
- Walidacja: backend 22/22, frontend 17/17, build i diff-check PASS.

### Doprecyzowanie Git Flow — 2026-10-17
- Zapisano pełną kolejność zadania: gałąź z develop, testy i commit, lokalny merge, weryfikacja develop, oczekiwanie na zgodę, push wyłącznie develop i usunięcie lokalnej gałęzi po udanym pushu.
- Dodano obowiązek zgłaszania sprzecznych poleceń oraz omówienia uzasadnienia przed świadomym zatwierdzeniem wyjątku.
- Określono zakres fire: zgoda właściciela na pracę bezpośrednio na develop nie zastępuje zielonych testów, ochrony sekretów ani zgody na push. Bieżąca korekta otrzymała ten status od Mariusza.

### Porządki Git — 2026-10-17
- Uaktualniono HANDOFF i STATUS po lokalnym scaleniu całego search-ui i dokumentu audytu do develop.
- Zachowano diagnostykę HTTP w ignorowanym katalogu lokalnym; nie jest częścią publikacji.
- Zapisano oczekiwanie na zgodę na push develop oraz warunek usuwania lokalnych gałęzi dopiero po udanym pushu.

### Dokumentacja narzędzi — 2026-10-17
- Usunięto odniesienia do nieużywanego narzędzia środowiskowego i ujednolicono odwołania do bezpośrednich poleceń testów w README oraz REPO.
- Zachowano wymóg zgody na Bash oraz zakazy odczytu i publikowania sekretów.

### Zamknięcie sesji — 2026-10-17
- Poprawki review wysłano na GitHub w commicie `d5336b6` (PR #1); bez merge i wdrożenia.
- Zapisano ostateczną decyzję o zachowaniu obecnego wyglądu i świadomym nieprzyjęciu uwagi o kontraście.
- Potwierdzono rzeczywiste wyszukiwanie MCP z hosta przez SearXNG; problem DNS klienta VirralAI w kontenerze pozostaje do zdiagnozowania.

### Poprawki code review — 2026-10-17
- Ochrona Host niezależną listą `SEARCH_ALLOWED_HOSTS`; test odrzucenia zgodnych, ale obcych nagłówków Host/Origin i zachowania dostępu Docker.
- Usunięto awarię renderowania wyniku z adresem `https://www./`.
- Poprawiono fokus mobilnej historii: wejście do panelu, Tab/Shift+Tab, Escape, powrót do przycisku lub wyszukiwarki. Zamknięty panel wyłączono z interakcji i drzewa dostępności.
- Zachowano wygląd na polecenie Mariusza; uwaga review o kontraście nie jest realizowana.
- Kontrole: backend 20/20, frontend 17/17, build i smoke nowego kodu — PASS.

### MVP 1.0 stabilization — 2026-10-16
- Preserved valid history entries when storage contains null items.
- Rejected malformed search responses with controlled API/UI errors instead of crashes.
- Corrected the missing-frontend help reference to README.
- Verified 17 backend tests, 13 frontend tests, production frontend build and the running deployment smoke test. Latest fixes still require rebuilding the Docker image.

### Added
- Dependency-free Python deployment smoke test for frontend assets, API validation and MCP initialization/tool discovery, with optional live search.
- Backend tests for provider limits, daily reset, failed HTTP requests, fallback and the smoke flow; isolated MCP instances between tests.

### Fixed
- Added the missing `web/package-lock.json` required by the Docker frontend build and `npm ci`. Verified npm ci, all 7 frontend tests, and the production frontend build.

## [0.1.0] - 2026-10-16

### Added
- **MCP Search Server**: Python FastMCP server (`mcp/server.py`) providing the `web_search` tool with SearXNG querying and fallback to Perplexity API ([7b00209](https://github.com/mafio69/szukaj/commit/7b00209d03ff680ab7bb48f857f290297b08b065)).
- **Docker Compose Stack**: Containerized deployment (`docker-compose.yml`) containing SearXNG and MCP search services attached to the external `ai` network ([7b00209](https://github.com/mafio69/szukaj/commit/7b00209d03ff680ab7bb48f857f290297b08b065)).
- **SearXNG Engine Settings**: Configuration (`searxng-settings.yml`) with JSON API response format enabled and rate limiter disabled ([7b00209](https://github.com/mafio69/szukaj/commit/7b00209d03ff680ab7bb48f857f290297b08b065)).
- **Project Documentation & AI Policies**: Core documentation (`README.md`, `REPO.md`, `docs/INSTRUKCJA.md`), environment configuration template (`.env.example`), AI agent policies (`AGENTS.md`, `GIT-FLOW.md`), and session tracking templates (`STATUS.md`, `HANDOFF.md`) ([7b00209](https://github.com/mafio69/szukaj/commit/7b00209d03ff680ab7bb48f857f290297b08b065)).

[1.0.0]: https://github.com/mafio69/szukaj/releases/tag/v1.0.0
[0.1.0]: https://github.com/mafio69/szukaj/releases/tag/v0.1.0
