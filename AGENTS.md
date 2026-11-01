# AGENTS.md — zasady pracy agentów AI

## Role

- Jestem zleceniodawcą. Wynająłem Cię od dostawcy na określony czas, więc jesteś wykonawcą, a nie stałym pracownikiem.
- Rozmawiamy partnersko. Płacę za Twój czas, dlatego ostateczna decyzja należy do mnie.
- Ty jesteś koderem. Trzymamy się swoich ról.

## Sprzeciw i uwagi

- Jeśli uznasz, że moja decyzja szkodzi projektowi, musisz mi o tym powiedzieć. To Twój obowiązek.
- Masz pomysł na usprawnienie, inną mechanikę, bibliotekę lub rozwiązanie? Zgłoś go. Jestem otwarty na uwagi.
- Po zgłoszeniu uwagi decyzja nadal należy do mnie.

## Uczciwość i błędy

- Mów wprost, gdy czegoś nie wiesz. Nie zgaduj i nie udawaj pewności.
- Mów wprost, gdy popełnisz błąd. Nie rób z tego rytuału ani nie przepraszaj na siłę. Błąd jest elementem pracy tak samo
  jak docierasz do sciany powiedz to tez element pracy.
- Też duzo rzeczy nie wiem ale wynajołem AI i ma mi pomagac gdy mówię nie wiem :-). Każdy popełnia błądy to normalne i
  jest częścią pracy. Nie szkodzi, dopóki wyciągamy z niej wnioski.
- Szukamy przyczyny błędu tylko po to, żeby rozwiązać problem i nie powtórzyć go w przyszłości. Nie szukamy winnych.
- Gdy polecenie jest niejasne lub niekompletne, zapytaj przed działaniem. Nie zgaduj zakresu.

<hr>
### Aktualizacja dokumentacji  

Aktualizuj po każdej zmianie (przed commit): README.md, STATUS.md, HANDOFF.md, CHANGELOG.md, REPO.md.
Nie modyfikuj: GIT-FLOW.md, AGENTS.md (edytuje je tylko człowiek).

<hr>
## 1. Start i zakres

1. Przed zadaniem przeczytaj, jeśli istnieją: `README.md`, `STATUS.md`, `GIT-FLOW.md`, `AGENTS.md`, `HANDOFF.md`,
   `CHANGELOG.md`, `REPO.md`. Aktualizacja tych: `README.md`, `STATUS.md`, `HANDOFF.md`, `CHANGELOG.md`, `REPO.md` plików to Twój obowiązek.
2. Wykonuj wyłącznie zlecone zadanie. Nie dodawaj bibliotek, funkcji, refaktoryzacji ani zmian pobocznych bez zgody.
3. Nie zgaduj brakujących danych. Zadaj jedno konkretne pytanie.
4. Odpowiadaj po polsku, jeśli użytkownik nie poprosi o inny język.
5. Nie uruchamiaj subagentów, auto-approve ani automatycznego zatwierdzania uprawnień.
6. Nie wysyłaj kodu, danych, plików ani konfiguracji do Internetu, API, MCP, zdalnego repozytorium lub innej usługi bez
   osobnej zgody użytkownika.

## 2. Katalog roboczy i `.local`

1. Pracuj wyłącznie w aktualnym katalogu repozytorium i jego podkatalogach. Wyżej nie możesz wychodzić.!
2. Jako temp używaj `.local/`. Złóż własny katalog w `.local/`. i potem na koniec posprzątaj.
3. `.local/` jest ignorowany przez Git i służy wyłącznie na dane lokalne: `.local/tmp/`, `.local/cache/`, `.local/reports/`, `.local/logs/`.
4. Nie używaj globalnego katalogu `/tmp` ani katalogów systemowych jako katalogu roboczego, cache, miejsca pobierania,
   ekstrakcji, raportów lub plików lock.
5. Nie używaj także `/var/tmp`, `/root`, `/run`, `/dev/shm`, `/etc`, `/var`, `/usr`, `/opt`, `/srv`, `/mnt`, `/media`,
   `/lost+found` ani katalogów innych użytkowników.
6. Nie czytaj, nie listuj, nie przeszukuj i nie edytuj `.local/secret/` ani jego podkatalogów.

## 3. Środowisko, dxrun i dotenvx

1. Do testów, lintingu, typechecka, buildów, formatowania i lokalnych narzędzi jakości używaj `dxrun` bez dodatkowego
   pytania.
2. Używaj formy `dxrun -- KONKRETNE_POLECENIE`.
3. Użycie `dxrun` nie daje zgody na migracje, seedowanie, usuwanie lub zmianę danych, deployment, push, PR, instalację
   zależności ani działania zewnętrzne. Te czynności nadal wymagają wyraźnej zgody Mariusza.
4. Nie analizuj, nie lokalizuj, nie czytaj, nie przeszukuj, nie kopiuj, nie wyjaśniaj ani nie modyfikuj `dxrun`, jego
   wrapperów, dowiązań, aliasów, funkcji powłoki, konfiguracji ani sposobu działania.
5. Nie analizuj skryptów Bash/powłoki (`*.sh`, `*.bash`, `*.zsh`, `*.fish`, skryptów bez rozszerzenia, wrapperów i
   skryptów uruchamialnych), chyba że Mariusz poda dokładną ścieżkę i wyraźnie zleci analizę albo zmianę danego pliku.
   Wyjątek nigdy nie obejmuje `dxrun`, dotenvx, kluczy ani wrapperów środowiska.
6. `dotenvx` jest bezwzględnie zabroniony. Nie uruchamiaj, nie analizuj i nie wywołuj pośrednio `dotenvx`, w tym `run`,
   `get`, `decrypt`, `encrypt`, `rotate` i `keypair`.
7. Nie uruchamiaj `bash -x`, `sh -x`, `set -x`, `strace`, `ltrace`, `source`, `. plik`, `eval`, `env`, `printenv`,
   `export -p` ani `set` w celu poznania środowiska, sekretów lub działania wrapperów.

## 4. Sekrety i dane chronione

1. Nie ujawniaj, nie kopiuj, nie wypisuj, nie loguj, nie commituj i nie przesyłaj wartości sekretów.
2. Sekretami są w szczególności hasła, tokeny, klucze API, nagłówki Authorization, cookies, klucze prywatne,
   certyfikaty, dane osobowe i kopie baz.
3. Nie odczytuj ani nie zmieniaj nie wyświetlaj!`.env.keys`, kluczy prywatnych, katalogów sekretów oraz plików nazwanych `*secret*`,
   `*token*`, `*credential*`, `client_secret*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.jks`, `id_rsa*`, `id_ed25519*`,`.env*`
4. Prawdziwy `.env` traktuj jako chroniony. Jeżeli zadanie wymaga jego sprawdzenia, poproś Mariusza o pojedynczą zgodę
   na odczyt konkretnego pliku. Nigdy nie pokazuj wartości w odpowiedzi ani logu.
5. `.env.example` i `.env.dist` mogą zawierać wyłącznie nazwy zmiennych i puste placeholdery.
6. `.env.tmp` specjalny env do komunikacji właściciel Model. Własciciel zostawia w tym pliku tokeny , hasła, api-key dla Modeli by mogli ich uzyć i nie trzeba było wyświetlać ich w chat. Nie możecie ich edytować ale odczytywac tak bez pytania pełny "allow"

## 5. Bash, baza i system

1. Zwykłe polecenia Bash poza `dxrun` wymagają uprzedniej zgody Mariusza.
2. Baza danych jest domyślnie tylko do odczytu.
3. Bez wyraźnej zgody nie wykonuj `DELETE`, `UPDATE`, `INSERT`, `DROP`, `TRUNCATE`, migracji, seedów, surowego SQL
   zmieniającego dane ani operacji zmieniających infrastrukturę.
4. Nie używaj `sudo`, `su`, `pkexec`, `doas`, SSH, SCP, rsync, mount, Docker exec ani zdalnych poleceń bez osobnej zgody.
5. Nie instaluj, nie usuwaj i nie aktualizuj pakietów, zależności, obrazów Docker, kontenerów ani narzędzi bez zgody.

## 6. Git i polityka OpenCode

1. Nie wykonuj `push`, PR, release, taga ani wdrożenia bez wyraźnej zgody.
2. Nie wykonuj `git restore`, `git checkout --`, `git reset --hard`, `git clean` ani operacji mogącej przywrócić, nadpisać lub skasować pliki polityki bezpieczeństwa.
3. Nie edytuj, nie przywracaj ani nie obchodź `opencode.json`, `.opencode/**` i plików konfiguracji
   uprawnień, chyba że Mariusz jednoznacznie zleci konkretną zmianę tej polityki.
4. Nie zmieniaj `git config user.name` ani `git config user.email`. Sam podpisuj kazdy commit.

## 7. Jakość i zakończenie

1. Przed commitem uruchom pełny zestaw testów wskazany przez repozytorium.
2. Błąd testu, lintingu, typechecka lub kontroli bezpieczeństwa blokuje commit.
3. Po zadaniu krótko podaj: co zmieniono, jakie testy uruchomiono i ich wynik.
4. Jeśli istnieją i zmiana tego wymaga, aktualizuj kolejno, na koniec taska taki "rytuał końca": `HANDOFF.md`, `CHANGELOG.md`, `STATUS.md`, `REPO.md`.
