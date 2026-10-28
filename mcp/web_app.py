"""Same-origin web UI and JSON adapter for the existing MCP search service."""

import contextlib
import html
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from access import McpAccessMiddleware
from app_logging import configure_logging, get_logger, is_dev_env
from server import CATEGORIES, HOST_PATTERN, TIME_RANGES, HOST, PORT, close_http_client, mcp, web_search

FRIENDLY_INTERNAL_ERROR = "Błąd. Przepraszamy, wystąpił problem techniczny. Spróbuj ponownie za moment."
UI_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def is_valid_result(result):
    if not isinstance(result, dict):
        return False
    if result.get("source") not in ("searxng", "perplexity-fast", None):
        return False
    items = result.get("results")
    if not isinstance(items, list):
        return False
    fields = ("title", "url", "snippet")
    for item in items:
        if not isinstance(item, dict):
            return False
        if any(item.get(field) is not None and not isinstance(item[field], str) for field in fields):
            return False
    return True


def _reject_search(logger, message: str, status_code: int) -> JSONResponse:
    logger.warning("Rejected /api/search request: %s (status=%d)", message, status_code)
    return JSONResponse({"error": message}, status_code=status_code)


def _gateway_error_response(dev_mode: bool, detail: str) -> JSONResponse:
    payload = {"error": "Search unavailable"}
    if dev_mode:
        payload["detail"] = detail
    return JSONResponse(payload, status_code=502)


def validated_advanced(advanced) -> dict:
    """Strict validation for browser UI; every violation raises ValueError."""
    if advanced is None:
        return {}
    if not isinstance(advanced, dict):
        raise ValueError("advanced must be an object")
    lists = {"exclude": 10, "include": 10, "site": 5, "not_site": 5}
    cleaned = {}
    for key, limit in lists.items():
        values = advanced.get(key, [])
        if not isinstance(values, list) or len(values) > limit:
            raise ValueError(f"advanced.{key} must be a list of at most {limit} items")
        for value in values:
            if not isinstance(value, str) or not value.strip() or len(value) > 100:
                raise ValueError(f"advanced.{key} items must be non-empty strings of at most 100 characters")
            if key in ("site", "not_site") and not HOST_PATTERN.fullmatch(value.strip()):
                raise ValueError(f"advanced.{key} items must be host names")
        cleaned[key] = [value.strip() for value in values]
    phrase = advanced.get("phrase", "")
    if not isinstance(phrase, str) or len(phrase) > 200:
        raise ValueError("advanced.phrase must be a string of at most 200 characters")
    cleaned["phrase"] = phrase
    language = advanced.get("language", "")
    if language and (not isinstance(language, str) or len(language) > 10):
        raise ValueError("advanced.language must be a short language code")
    cleaned["language"] = language
    time_range = advanced.get("time_range", "")
    if time_range and time_range not in TIME_RANGES:
        raise ValueError("advanced.time_range must be day, week, month or year")
    cleaned["time_range"] = time_range
    categories = advanced.get("categories", [])
    if not isinstance(categories, list) or len(categories) > 5:
        raise ValueError("advanced.categories must be a list of at most 5 items")
    for category in categories:
        if category not in CATEGORIES:
            raise ValueError("advanced.categories contains an unknown category")
    cleaned["categories"] = categories
    return cleaned


def _wants_html_error(request: Request) -> bool:
    if request.url.path.startswith(("/api/", "/mcp")):
        return False
    return "text/html" in request.headers.get("accept", "")


def _render_unhandled_error(request: Request, exc: Exception, dev_mode: bool):
    detail = f"{type(exc).__name__}: {exc}"
    if _wants_html_error(request):
        extra = f"<pre>{html.escape(detail)}</pre>" if dev_mode else ""
        body = (
            '<!doctype html><html lang="pl"><head><meta charset="utf-8">'
            "<title>szukaj.dom</title></head><body>"
            '<main role="alert"><h1>Błąd. Przepraszamy</h1>'
            f"<p>{FRIENDLY_INTERNAL_ERROR}</p>{extra}</main></body></html>"
        )
        return HTMLResponse(body, status_code=500, headers=UI_SECURITY_HEADERS)
    payload = {"error": FRIENDLY_INTERNAL_ERROR}
    if dev_mode:
        payload["detail"] = detail
    return JSONResponse(payload, status_code=500)


def create_app(search_service=web_search, static_dir=None, allowed_hosts=None, mcp_auth=None, app_env=None):
    assets = Path(static_dir) if static_dir else Path(__file__).resolve().parent / "static"
    dev_mode = is_dev_env(app_env)
    logger = get_logger()
    trusted_hosts = allowed_hosts if allowed_hosts is not None else [
        host.strip() for host in (os.getenv("SEARCH_ALLOWED_HOSTS")
                                  or "127.0.0.1,localhost,mcp-search").split(",") if host.strip()
    ]

    async def search_endpoint(request: Request):
        # Do not accept cross-origin form submissions or send provider errors to browsers.
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            return _reject_search(logger, "JSON required", 415)
        origin = request.headers.get("origin")
        if origin:
            origin_host = urlsplit(origin).hostname
            is_same_origin = origin == f"{request.url.scheme}://{request.url.netloc}"
            is_trusted = origin_host in trusted_hosts or origin_host == request.url.hostname
            if not (is_same_origin or is_trusted):
                return _reject_search(logger, "Origin not allowed", 403)
            if request.headers.get("sec-fetch-site") == "cross-site" and not is_trusted:
                return _reject_search(logger, "Origin not allowed", 403)
        elif request.headers.get("sec-fetch-site") == "cross-site":
            return _reject_search(logger, "Origin not allowed", 403)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return _reject_search(logger, "Request too large", 413)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return _reject_search(logger, "Invalid JSON", 400)
        if not isinstance(payload, dict):
            return _reject_search(logger, "Object required", 400)
        query = payload.get("query")
        count = payload.get("max_results", 10)
        is_invalid_query = not isinstance(query, str) or not query.strip() or len(query) > 500
        is_invalid_count = type(count) is not int or not 1 <= count <= 10
        if is_invalid_query or is_invalid_count:
            return _reject_search(logger, "Invalid search arguments", 400)
        try:
            advanced = validated_advanced(payload.get("advanced"))
        except ValueError as error:
            return _reject_search(logger, f"Invalid search arguments ({error})", 400)
        try:
            result = json.loads(await search_service(query.strip(), count, **advanced))
            if not is_valid_result(result):
                raise ValueError("Invalid search result")
        except Exception as exc:
            logger.error("Search service failure on /api/search: %s", type(exc).__name__, exc_info=True)
            return _gateway_error_response(dev_mode, f"{type(exc).__name__}: {exc}")
        if result.get("status") == "error" or result.get("errors"):
            provider_codes = ",".join(str(item) for item in result.get("errors", []))
            logger.error("Search providers unavailable on /api/search: %s", provider_codes or "status=error")
            return _gateway_error_response(dev_mode, f"Provider errors: {provider_codes or 'status=error'}")
        # Raw exception strings from providers can contain operational details.
        logger.info("Completed /api/search via %s (%d results)", result.get("source"), len(result.get("results", [])))
        return JSONResponse({"status": result.get("status", "ok" if result["results"] else "empty"),
                             "source": result.get("source"), "results": result.get("results", [])})

    async def index(request: Request):
        if not (assets / "index.html").is_file():
            logger.warning("Frontend index.html missing in %s", assets)
            return JSONResponse({"error": "Frontend not built. See README.md."}, status_code=503)
        return FileResponse(assets / "index.html", headers={
            "Cache-Control": "no-cache",
            **UI_SECURITY_HEADERS,
        })

    async def favicon(request: Request):
        if not (assets / "favicon.svg").is_file():
            return JSONResponse({"error": "Not found"}, status_code=404)
        return FileResponse(assets / "favicon.svg", headers=UI_SECURITY_HEADERS)

    async def handle_unhandled_error(request: Request, exc: Exception):
        logger.error(
            "Unhandled error on %s %s: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc_info=exc,
        )
        return _render_unhandled_error(request, exc, dev_mode)

    # Reuse FastMCP's application, including its existing session-manager lifespan.
    app = mcp.streamable_http_app()
    mcp_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(application):
        async with mcp_lifespan(application) as state:
            try:
                yield state
            finally:
                await close_http_client()

    app.router.lifespan_context = lifespan
    app.add_exception_handler(Exception, handle_unhandled_error)
    app.add_exception_handler(500, handle_unhandled_error)
    app.add_middleware(McpAccessMiddleware, auth_value=(
        os.getenv("MCP_AUTH_TOKEN", "") if mcp_auth is None else mcp_auth
    ))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts,
                       www_redirect=False)
    app.router.routes[0:0] = [
        Route("/", index),
        Route("/favicon.svg", favicon),
        Route("/api/search", search_endpoint, methods=["POST"]),
        Mount("/assets", app=StaticFiles(directory=assets / "assets", check_dir=False)),
    ]
    return app


if __name__ == "__main__":
    configure_logging()
    uvicorn.run(create_app(), host=HOST, port=PORT, access_log=False)
