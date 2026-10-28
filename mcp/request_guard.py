"""Shared validation for browser JSON POST requests: content type, origin and size."""

import json
from urllib.parse import urlsplit

from starlette.requests import Request

MAX_BODY_BYTES = 4096


class RejectedRequest(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def check_origin(request: Request, trusted_hosts) -> None:
    # Do not accept cross-origin form submissions from other sites.
    origin = request.headers.get("origin")
    if origin:
        origin_host = urlsplit(origin).hostname
        is_same_origin = origin == f"{request.url.scheme}://{request.url.netloc}"
        is_trusted = origin_host in trusted_hosts or origin_host == request.url.hostname
        if not (is_same_origin or is_trusted):
            raise RejectedRequest("Origin not allowed", 403)
        if request.headers.get("sec-fetch-site") == "cross-site" and not is_trusted:
            raise RejectedRequest("Origin not allowed", 403)
    elif request.headers.get("sec-fetch-site") == "cross-site":
        raise RejectedRequest("Origin not allowed", 403)


async def read_json_object(request: Request, trusted_hosts) -> dict:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise RejectedRequest("JSON required", 415)
    check_origin(request, trusted_hosts)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise RejectedRequest("Request too large", 413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise RejectedRequest("Invalid JSON", 400) from None
    if not isinstance(payload, dict):
        raise RejectedRequest("Object required", 400)
    return payload
