"""Email/password accounts for the browser UI: login, registration and password reset."""

import asyncio
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app_logging import ROOT, get_logger
from auth_store import DUMMY_HASH, AuthStore, verify_password
from mailer import MailerUnavailable, SmtpMailer
from request_guard import RejectedRequest, read_json_object

SESSION_COOKIE = "szukaj_session"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN, PASSWORD_MAX = 10, 256
ACCEPTED_MESSAGE = "Jeśli adres jest uprawniony, wysłaliśmy na niego link z potwierdzeniem."
DEFAULT_DB_PATH = ROOT / ".local" / "data" / "szukaj.db"


def is_auth_enabled(raw: str | None = None) -> bool:
    value = os.getenv("AUTH_ENABLED", "") if raw is None else raw
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_email(value) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    return email if len(email) <= 254 and EMAIL_PATTERN.match(email) else None


def is_valid_password(value) -> bool:
    return isinstance(value, str) and PASSWORD_MIN <= len(value) <= PASSWORD_MAX


class RateLimiter:
    """In-process sliding window; resets on restart like the Perplexity counter."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        hits = self.hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


class Auth:
    def __init__(self, store, mailer, allowed_emails=(), public_url="", trusted_hosts=()):
        self.store = store
        self.mailer = mailer
        self.allowed_emails = {email.strip().lower() for email in allowed_emails if email.strip()}
        self.public_url = public_url.rstrip("/")
        self.trusted_hosts = list(trusted_hosts)
        self.secure_cookie = self.public_url.startswith("https://")
        self.mail_limit = RateLimiter(3, 60 * 60)
        self.login_limit = RateLimiter(10, 15 * 60)
        self.logger = get_logger()

    @classmethod
    def from_env(cls, trusted_hosts):
        allowed = (os.getenv("AUTH_ALLOWED_EMAILS") or "").split(",")
        store = AuthStore(Path(os.getenv("AUTH_DB_PATH") or DEFAULT_DB_PATH))
        return cls(store, SmtpMailer(), allowed, os.getenv("APP_PUBLIC_URL", ""), trusted_hosts)

    def current_user(self, request: Request):
        return self.store.session_user(request.cookies.get(SESSION_COOKIE))

    def _reject(self, error: RejectedRequest) -> JSONResponse:
        self.logger.warning("Rejected auth request: %s (status=%d)", error.message, error.status_code)
        return JSONResponse({"error": error.message}, status_code=error.status_code)

    def _signed_in(self, user, status_code=200) -> JSONResponse:
        response = JSONResponse({"user": {"email": user["email"]}}, status_code=status_code)
        response.set_cookie(SESSION_COOKIE, self.store.create_session(user["id"]), max_age=30 * 24 * 60 * 60,
                            path="/", httponly=True, samesite="lax", secure=self.secure_cookie)
        return response

    async def _credentials(self, request: Request):
        payload = await read_json_object(request, self.trusted_hosts)
        email = normalize_email(payload.get("email"))
        password = payload.get("password")
        if email is None or not is_valid_password(password):
            raise RejectedRequest("Invalid email or password format", 400)
        return email, password

    async def me(self, request: Request):
        user = self.current_user(request)
        return JSONResponse({"enabled": True, "user": {"email": user["email"]} if user else None})

    async def login(self, request: Request):
        try:
            email, password = await self._credentials(request)
        except RejectedRequest as error:
            return self._reject(error)
        if not self.login_limit.allow(f"{email}|{request.client.host if request.client else ''}"):
            return JSONResponse({"error": "Too many attempts"}, status_code=429)
        user = await asyncio.to_thread(self.store.authenticate, email, password)
        if user is None:
            self.logger.info("Failed login attempt")
            return JSONResponse({"error": "Invalid credentials"}, status_code=401)
        return self._signed_in(user)

    async def logout(self, request: Request):
        try:
            await read_json_object(request, self.trusted_hosts)
        except RejectedRequest as error:
            return self._reject(error)
        self.store.delete_session(request.cookies.get(SESSION_COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=self.secure_cookie)
        return response

    async def _request_link(self, request: Request, purpose: str):
        try:
            email, password = await self._credentials(request)
        except RejectedRequest as error:
            return self._reject(error)
        if not self.mailer.available:
            self.logger.error("Account email requested but SMTP is not configured")
            return JSONResponse({"error": "Email unavailable"}, status_code=503)
        if not self.mail_limit.allow(email):
            return JSONResponse({"error": "Too many attempts"}, status_code=429)
        eligible = purpose == "reset" or email in self.allowed_emails
        token = await asyncio.to_thread(self.store.issue_token, email, purpose, password) if eligible else None
        if token is None:
            # Same cost and answer whether or not the account exists.
            if not eligible:
                await asyncio.to_thread(verify_password, password, DUMMY_HASH)
            return JSONResponse({"message": ACCEPTED_MESSAGE}, status_code=202)
        base = self.public_url or str(request.base_url).rstrip("/")
        link = f"{base}/?confirm={token}"
        return JSONResponse({"message": ACCEPTED_MESSAGE}, status_code=202,
                            background=BackgroundTask(self._send, email, purpose, link))

    async def _send(self, email: str, purpose: str, link: str) -> None:
        try:
            await self.mailer.send_link(email, purpose, link)
        except MailerUnavailable as exc:
            self.logger.error("Sending %s email failed: %s", purpose, exc)

    async def register(self, request: Request):
        return await self._request_link(request, "register")

    async def password_reset(self, request: Request):
        return await self._request_link(request, "reset")

    async def confirm(self, request: Request):
        try:
            payload = await read_json_object(request, self.trusted_hosts)
        except RejectedRequest as error:
            return self._reject(error)
        token = payload.get("token")
        if not isinstance(token, str) or not 0 < len(token) <= 128:
            return JSONResponse({"error": "Invalid token"}, status_code=400)
        user = await asyncio.to_thread(self.store.confirm, token)
        if user is None:
            return JSONResponse({"error": "Invalid or expired token"}, status_code=400)
        self.logger.info("Account email token confirmed")
        return self._signed_in(user)

    def routes(self) -> list[Route]:
        return [
            Route("/api/auth/me", self.me, methods=["GET"]),
            Route("/api/auth/login", self.login, methods=["POST"]),
            Route("/api/auth/logout", self.logout, methods=["POST"]),
            Route("/api/auth/register", self.register, methods=["POST"]),
            Route("/api/auth/password-reset", self.password_reset, methods=["POST"]),
            Route("/api/auth/confirm", self.confirm, methods=["POST"]),
        ]


async def auth_disabled(request: Request):
    return JSONResponse({"enabled": False, "user": None})
