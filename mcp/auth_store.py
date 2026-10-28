"""SQLite-backed accounts: password hashes, one-time email tokens and sessions."""

import base64
import contextlib
import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
TOKEN_TTL = 60 * 60
SESSION_TTL = 30 * 24 * 60 * 60
PURPOSES = ("register", "reset")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT,
    verified_at INTEGER,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
"""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        scheme, n, r, p, salt, digest = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                                dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Equalises login timing for unknown accounts.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthStore:
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    @contextlib.contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db
        finally:
            db.close()

    def _now(self) -> int:
        return int(self.clock())

    def find_user(self, email: str):
        with self._connect() as db:
            return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def authenticate(self, email: str, password: str):
        user = self.find_user(email)
        if user is None or user["verified_at"] is None:
            verify_password(password, DUMMY_HASH)
            return None
        return user if verify_password(password, user["password_hash"]) else None

    def issue_token(self, email: str, purpose: str, password: str) -> str | None:
        """Stores the pending password; it becomes active only after confirm()."""
        if purpose not in PURPOSES:
            raise ValueError("Unknown token purpose")
        pending_hash = hash_password(password)
        token = secrets.token_urlsafe(32)
        now = self._now()
        with self._connect() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if purpose == "register":
                if user is not None and user["verified_at"] is not None:
                    return None
                if user is None:
                    user_id = db.execute("INSERT INTO users (email, created_at) VALUES (?, ?)",
                                         (email, now)).lastrowid
                else:
                    user_id = user["id"]
            else:
                if user is None or user["verified_at"] is None:
                    return None
                user_id = user["id"]
            db.execute("DELETE FROM email_tokens WHERE user_id = ? OR expires_at <= ?", (user_id, now))
            db.execute("INSERT INTO email_tokens VALUES (?, ?, ?, ?, ?)",
                       (_token_hash(token), user_id, purpose, pending_hash, now + TOKEN_TTL))
        return token

    def confirm(self, token: str):
        """Activates the pending password, revokes old sessions and returns the user."""
        now = self._now()
        with self._connect() as db:
            row = db.execute("DELETE FROM email_tokens WHERE token_hash = ? RETURNING *",
                             (_token_hash(token),)).fetchone()
            if row is None or row["expires_at"] <= now:
                return None
            db.execute("UPDATE users SET password_hash = ?, verified_at = COALESCE(verified_at, ?) WHERE id = ?",
                       (row["password_hash"], now, row["user_id"]))
            db.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
            return db.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = self._now()
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (_token_hash(token), user_id, now + SESSION_TTL))
        return token

    def session_user(self, token: str | None):
        if not token:
            return None
        with self._connect() as db:
            return db.execute(
                "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (_token_hash(token), self._now())).fetchone()

    def delete_session(self, token: str | None) -> None:
        if token:
            with self._connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
