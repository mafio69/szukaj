import datetime
import json
import os
import re
from threading import Lock
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from app_logging import get_logger

SEARXNG_URL = os.getenv("SEARXNG_URL") or "http://searxng:8080"
SEARXNG_LANG = os.getenv("SEARXNG_LANG") or "auto"
PPLX_KEY = os.getenv("PPLX_API_KEY", "")
PPLX_DAILY_LIMIT = int(os.getenv("PPLX_DAILY_LIMIT") or "50")
HOST = os.getenv("MCP_HOST") or "0.0.0.0"
PORT = int(os.getenv("MCP_PORT") or "8000")

TIME_RANGES = ("day", "week", "month", "year")
CATEGORIES = ("general", "images", "videos", "news", "it", "music", "files", "science", "social media")
LANGUAGE_PATTERN = re.compile(r"^(?:auto|all|[a-z]{2}(?:-[A-Z]{2})?)$")
HOST_PATTERN = re.compile(r"^(?:\*\.)?[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")
TERM_LENGTH = 100
TERM_LIMIT = 10
HOST_LIMIT = 5


def clean_term(value) -> str:
    """Quote-safe search term: engine operators inside terms must stay inert."""
    if not isinstance(value, str):
        return ""
    return value.replace('"', "").replace("\\", "").strip()


def sanitize_terms(values, limit=TERM_LIMIT) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    terms: list[str] = []
    for value in values:
        term = clean_term(value)[:TERM_LENGTH]
        if term and term not in terms:
            terms.append(term)
    return terms[:limit]


def sanitize_hosts(values, limit=HOST_LIMIT) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    hosts: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        host = value.strip().removeprefix("https://").removeprefix("http://").split("/", 1)[0]
        if HOST_PATTERN.fullmatch(host) and host not in hosts:
            hosts.append(host)
    return hosts[:limit]


def build_detailed_query(query: str, *, exclude=(), include=(), phrase="", site=(), not_site=()) -> str:
    """Append engine operators (passed verbatim to external engines) to the query."""
    parts = [query.strip()] if query.strip() else []
    parts += [f'-"{clean_term(term)}"' for term in exclude if clean_term(term)]
    parts += [f'+"{clean_term(term)}"' for term in include if clean_term(term)]
    clean_phrase = clean_term(phrase)[:2 * TERM_LENGTH]
    if clean_phrase:
        parts.append(f'"{clean_phrase}"')
    parts += [f"site:{host}" for host in site]
    parts += [f"-site:{host}" for host in not_site]
    return " ".join(part for part in parts if part)


mcp = FastMCP("search", host=HOST, port=PORT)
_pplx = {"day": None, "count": 0}
_pplx_lock = Lock()
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(follow_redirects=False)
    return _http_client


async def close_http_client() -> None:
    global _http_client
    client, _http_client = _http_client, None
    if client is not None and not client.is_closed:
        await client.aclose()


class ProviderUnavailable(RuntimeError):
    """Controlled local reason; never carries provider response details."""


def _error_code(provider, error):
    if isinstance(error, ProviderUnavailable) and str(error) in ("perplexity_no_key", "perplexity_limit"):
        return str(error)
    if isinstance(error, httpx.TimeoutException):
        return provider + "_timeout"
    if isinstance(error, httpx.HTTPError):
        return provider + "_http_error"
    return provider + "_error"


async def _searxng(q: str, n: int, time_range: str = "", language: str = "", categories: list[str] | None = None) -> list[dict]:
    params = {"q": q, "format": "json", "language": language or SEARXNG_LANG}
    if time_range in TIME_RANGES:
        params["time_range"] = time_range
    valid_categories = [category for category in (categories or []) if category in CATEGORIES]
    if valid_categories:
        params["categories"] = ",".join(valid_categories)
    r = await get_http_client().get(
        f"{SEARXNG_URL}/search",
        params=params,
        headers={"X-Forwarded-For": "127.0.0.1"},
        timeout=10,
    )
    r.raise_for_status()
    out = r.json().get("results", [])[:n]
    return [
        {"title": x.get("title"), "url": x.get("url"),
          "snippet": (x.get("content") or "")[:400]}
        for x in out
    ]


async def _perplexity(q: str, n: int) -> list[dict]:
    if not PPLX_KEY:
        raise ProviderUnavailable("perplexity_no_key")
    today = datetime.date.today().isoformat()
    # Reserve before HTTP. Failures/cancellation may still have incurred costs.
    # The lock never covers network I/O or an await.
    with _pplx_lock:
        if _pplx["day"] != today:
            _pplx.update(day=today, count=0)
        if _pplx["count"] >= PPLX_DAILY_LIMIT:
            raise ProviderUnavailable("perplexity_limit")
        _pplx["count"] += 1
    r = await get_http_client().post(
        "https://api.perplexity.ai/search",
        headers={"Authorization": f"Bearer {PPLX_KEY}"},
        json={"query": q, "max_results": n, "search_type": "fast"},
        timeout=20,
    )
    r.raise_for_status()
    return [
        {"title": x.get("title"), "url": x.get("url"),
         "snippet": (x.get("snippet") or "")[:400]}
        for x in r.json().get("results", [])[:n]
    ]


@mcp.tool()
async def web_search(
    query: Annotated[str, Field(min_length=1, max_length=1000)],
    max_results: int = 5,
    time_range: str = "",
    language: str = "",
    categories: list[str] | None = None,
    exclude: list[str] | None = None,
    include: list[str] | None = None,
    phrase: str = "",
    site: list[str] | None = None,
    not_site: list[str] | None = None,
) -> str:
    """Wyszukaj w internecie. JSON: status ok/empty/error, source, results, errors.

    Szczegółowe opcje: time_range (day/week/month/year), language (np. pl, auto),
    categories (np. ["general","news"]; general, images, videos, news, it, music,
    files, science, social media), exclude/include (słowa wykluczone/wymagane),
    phrase (dokładna fraza), site/not_site (domeny ograniczające/wykluczające).
    Operatory -/+/"..."/site: są przekazywane do zewnętrznych silników.
    """
    logger = get_logger()
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        logger.warning("Rejected invalid MCP web_search query")
        raise ValueError("query must contain 1–1000 characters")
    query = query.strip()
    n = max(1, min(max_results, 10))
    if time_range and time_range not in TIME_RANGES:
        raise ValueError(f"time_range must be one of {TIME_RANGES}")
    if language and not LANGUAGE_PATTERN.fullmatch(language):
        raise ValueError("language must be e.g. pl, en-US, auto or all")
    for category in categories or []:
        if category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
    options = {
        "exclude": sanitize_terms(exclude),
        "include": sanitize_terms(include),
        "phrase": clean_term(phrase),
        "site": sanitize_hosts(site),
        "not_site": sanitize_hosts(not_site),
    }
    detailed = build_detailed_query(query, **options)
    if len(detailed) > 1000:
        raise ValueError("query with detailed options must stay within 1000 characters")
    query = detailed
    searxng_options = {"time_range": time_range, "language": language, "categories": categories}
    logger.debug("Starting web_search (max_results=%d, query_len=%d, options=%s)", n, len(query),
                 ",".join(key for key, value in searxng_options.items() if value))
    errors = []
    try:
        res = await _searxng(query, n, **{key: value for key, value in searxng_options.items() if value})
        if res:
            logger.info("Search succeeded via searxng (%d results)", len(res))
            return json.dumps({"status": "ok", "source": "searxng", "results": res, "errors": []}, ensure_ascii=False)
    except Exception as e:
        code = _error_code("searxng", e)
        errors.append(code)
        logger.warning("Primary provider searxng failed: %s (%s)", code, type(e).__name__)
    try:
        res = await _perplexity(query, n)
        if res:
            logger.info("Search succeeded via perplexity-fast (%d results)", len(res))
            return json.dumps({"status": "ok", "source": "perplexity-fast", "results": res, "errors": []}, ensure_ascii=False)
    except Exception as e:
        code = _error_code("perplexity", e)
        # An unconfigured optional fallback is disabled, not a failed search.
        if code != "perplexity_no_key" or errors:
            errors.append(code)
        if code != "perplexity_no_key":
            logger.warning("Fallback provider perplexity failed: %s (%s)", code, type(e).__name__)
    if errors:
        logger.error("Search failed for all providers: %s", ",".join(errors))
    else:
        logger.info("Search returned empty results")
    return json.dumps({"status": "error" if errors else "empty", "source": None,
                       "results": [], "errors": errors}, ensure_ascii=False)


if __name__ == "__main__":
    import uvicorn
    from access import McpAccessMiddleware

    app = McpAccessMiddleware(mcp.streamable_http_app(), os.getenv("MCP_AUTH_TOKEN", ""))
    uvicorn.run(app, host=HOST, port=PORT, access_log=False)
