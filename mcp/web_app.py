"""Same-origin web UI and JSON adapter for the existing MCP search service."""

import contextlib
import html
import json
import os
from pathlib import Path

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from access import McpAccessMiddleware
from app_logging import configure_logging, get_logger, is_dev_env
from auth_routes import Auth, auth_disabled, is_auth_enabled
from request_guard import RejectedRequest, read_json_object
from server import HOST, PORT, close_http_client, mcp, web_search

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


def create_app(search_service=web_search, static_dir=None, allowed_hosts=None, mcp_auth=None, app_env=None,
               auth=None):
    """`auth`: None reads AUTH_ENABLED from the environment, False disables accounts."""
    assets = Path(static_dir) if static_dir else Path(__file__).resolve().parent / "static"
    dev_mode = is_dev_env(app_env)
    logger = get_logger()
    trusted_hosts = allowed_hosts if allowed_hosts is not None else [
        host.strip() for host in (os.getenv("SEARCH_ALLOWED_HOSTS")
                                  or "127.0.0.1,localhost,mcp-search").split(",") if host.strip()
    ]
    if auth is None:
        auth = Auth.from_env(trusted_hosts) if is_auth_enabled() else False
    auth = auth or None
    auth_routes = auth.routes() if auth else [Route("/api/auth/me", auth_disabled, methods=["GET"])]

    async def search_endpoint(request: Request):
        # Do not send provider errors to browsers.
        try:
            payload = await read_json_object(request, trusted_hosts)
        except RejectedRequest as error:
            return _reject_search(logger, error.message, error.status_code)
        if auth is not None and auth.current_user(request) is None:
            return _reject_search(logger, "Login required", 401)
        query = payload.get("query")
        count = payload.get("max_results", 10)
        is_invalid_query = not isinstance(query, str) or not query.strip() or len(query) > 500
        is_invalid_count = type(count) is not int or not 1 <= count <= 10
        if is_invalid_query or is_invalid_count:
            return _reject_search(logger, "Invalid search arguments", 400)
        try:
            result = json.loads(await search_service(query.strip(), count))
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
        *auth_routes,
        Mount("/assets", app=StaticFiles(directory=assets / "assets", check_dir=False)),
    ]
    return app


if __name__ == "__main__":
    configure_logging()
    uvicorn.run(create_app(), host=HOST, port=PORT, access_log=False)
