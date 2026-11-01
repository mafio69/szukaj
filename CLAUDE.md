# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

`AGENTS.md` (this repo) and `../AGENTS.md` (parent) are binding and override defaults. The essentials:

- Talk to the user in **Polish**; code, identifiers, commit messages and technical docs in **English**.
- Never read, print or scan secrets: `.env`, `.env.*`, `.local/secret/`, `http/http-client.private.env.json`, anything matching `*secret*`/`*token*`/`*credential*`, `~/.config/gcloud`, etc. No `env`/`printenv`/`dotenvx`. Do not analyze `dxrun`, `dotenvx` or environment scripts.
- Branch from `origin/develop` (never work on `master`/`develop` directly). Agent may commit itself (with `Co-Authored-By` trailer); `git push`, deploy and branch deletion need explicit consent in the current conversation. No `--no-verify`, no force push, no `git restore`/`reset --hard`/`clean -f` without consent.
- Stay in the requested scope; no new dependencies or package upgrades without consent. Report out-of-scope problems instead of fixing them.
- After finishing: update `HANDOFF.md` → `CHANGELOG.md` (append-only) → `STATUS.md` (each has a "how to maintain" section at the top).
- Be frugal with bash and don't dig through git history (`log`/`show`/`blame`) — ask instead.

## Commands

```bash
python3 scripts/check_project.py          # mandatory pre-commit gate; must be green
```
Runs in order, stops at first failure, logs to `.local/logs/checks/<name>.log`: ruff (`mcp scripts tests`) → `check_tracked_files.py` (secret scanner for tracked/staged files) → backend unittest → `npm --prefix web test` → `npm --prefix web run build` → `git diff --check` (worktree + staged). Ruff is pinned (`requirements-dev.txt`) and installed into `.local/tools/ruff`; backend deps may live in `.local/python` — the gate adds both to `PYTHONPATH`. See README "Pre-Commit Quality Checks" for the one-time Ruff install.

```bash
python3 -m unittest discover -s tests -v                      # backend tests
python3 -m unittest tests.test_search_status -v               # single module
python3 -m unittest tests.test_search_status.SearchStatusTests.test_invalid_queries_never_call_providers
npm --prefix web test                                         # Vitest (web/src/App.test.jsx)
npm --prefix web run dev                                      # Vite dev UI, proxies /api to :8890
docker compose up -d --build                                  # full stack (needs `docker network create ai` and .env)
python3 scripts/smoke_test.py [--url http://szukaj.dom]       # deployment smoke; --query does a real (possibly paid) search
```

There is no `pytest`; tests are stdlib `unittest` and insert `mcp/` into `sys.path` before importing (`import server`, `import web_app`) — hence the E402 ignore for `tests/`.

## Architecture

Single Python service (`mcp/`) serving three things from one ASGI app, plus a SearXNG container:

- `mcp/server.py` — the search engine. FastMCP v1 tool `web_search(query, max_results)` with a provider chain: **SearXNG → Perplexity → Gemini (Google Search grounding)**. Each fallback runs only when the previous one returned empty or raised. Missing API keys (`*_no_key`) mean "disabled", not an error. Returns a JSON **string** `{status: ok|empty|error, source, results[{title,url,snippet≤400}], errors[codes]}`; error codes come from `_error_code()` and must never leak raw exceptions/secrets. One shared `httpx.AsyncClient` (`get_http_client`/`close_http_client`). Perplexity has an in-memory, per-process daily limit reserved atomically under a short lock (reset on restart — intentional).
- `mcp/web_app.py` — `create_app(...)` (Starlette, run by Uvicorn, the container entrypoint). Mounts `POST /api/search` (browser API: JSON only, ≤4096 B body, query ≤500 chars, same-origin checks, 502 on provider failure with friendly Polish message unless `APP_ENV=dev`), the MCP Streamable HTTP transport at `/mcp`, and the built React UI from `static/`. `TrustedHostMiddleware` driven by `SEARCH_ALLOWED_HOSTS`. `create_app` takes injectable `search_service`, `static_dir`, `allowed_hosts`, `mcp_auth`, `app_env` — tests use these instead of patching globals. FastMCP's session manager can start once per instance, so tests build isolated app instances.
- `mcp/access.py` — `McpAccessMiddleware`: optional `MCP_AUTH_TOKEN` Bearer check (constant-time) on all `/mcp` methods. Not a UI login.
- `mcp/app_logging.py` — rotating, gzip-compressed file logging (`LOG_*` env vars).
- `web/src/` — React 19 + Vite UI: `App.jsx` (search states, cancels/discards stale responses), `api.js` (validates response shape, only http/https URLs), `storage.js` (localStorage history, max 30).

`python mcp/server.py` starts MCP alone; the full app starts via `mcp/web_app.py`. The Dockerfile builds the frontend in a Node 24 stage and copies `dist` into `/app/static`; only the four `mcp/*.py` files are copied, so a new backend module must be added to the `COPY` line.

Compose: SearXNG service is named **`szukaj`** (README still says `searxng`), image pinned by sha256 digest, config mounted read-only from `searxng-settings.example.yml` (secret comes only from `SEARXNG_SECRET`). `mcp-search` runs as UID 10001, published on `127.0.0.1:8890` by default, both on the external `ai` network. MCP contract details: `docs/MCP-USAGE.md`; tech map (Polish): `REPO.md`.
