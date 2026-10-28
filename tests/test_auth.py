import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

from starlette.testclient import TestClient
import auth_store
import server
from auth_routes import Auth, RateLimiter, normalize_email
from auth_store import AuthStore, hash_password, verify_password
from mailer import SmtpMailer, compose_message
from web_app import create_app

PASSWORD = "correct horse battery"
NEW_PASSWORD = "another long secret"


class FakeMailer:
    available = True

    def __init__(self):
        self.sent = []

    async def send_link(self, recipient, purpose, link):
        self.sent.append((recipient, purpose, link))

    def token(self):
        return parse_qs(urlsplit(self.sent[-1][2]).query)["confirm"][0]


class Clock:
    def __init__(self):
        self.now = 1_000_000

    def __call__(self):
        return self.now


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.clock = Clock()
        self.store = AuthStore(Path(directory.name) / "nested" / "auth.db", clock=self.clock)

    def register(self, email="ala@example.org", password=PASSWORD):
        return self.store.confirm(self.store.issue_token(email, "register", password))

    def test_password_hash_round_trip_and_rejects_garbage(self):
        stored = hash_password(PASSWORD)
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(verify_password(PASSWORD, stored))
        self.assertFalse(verify_password("wrong password", stored))
        for broken in (None, "", "plain", "md5$1$2$3$aa$bb", "scrypt$x$8$1$aa$bb"):
            self.assertFalse(verify_password(PASSWORD, broken))

    def test_registration_is_inactive_until_confirmed(self):
        token = self.store.issue_token("ala@example.org", "register", PASSWORD)
        self.assertIsNone(self.store.authenticate("ala@example.org", PASSWORD))
        self.assertEqual(self.store.confirm(token)["email"], "ala@example.org")
        self.assertIsNotNone(self.store.authenticate("ala@example.org", PASSWORD))

    def test_tokens_are_single_use_and_expire(self):
        token = self.store.issue_token("ala@example.org", "register", PASSWORD)
        self.assertIsNotNone(self.store.confirm(token))
        self.assertIsNone(self.store.confirm(token))
        expired = self.store.issue_token("ala@example.org", "reset", NEW_PASSWORD)
        self.clock.now += auth_store.TOKEN_TTL
        self.assertIsNone(self.store.confirm(expired))
        self.assertIsNotNone(self.store.authenticate("ala@example.org", PASSWORD))

    def test_reset_keeps_old_password_until_confirmed_and_revokes_sessions(self):
        user = self.register()
        session = self.store.create_session(user["id"])
        token = self.store.issue_token("ala@example.org", "reset", NEW_PASSWORD)
        self.assertIsNotNone(self.store.authenticate("ala@example.org", PASSWORD))
        self.assertIsNone(self.store.authenticate("ala@example.org", NEW_PASSWORD))
        self.store.confirm(token)
        self.assertIsNone(self.store.authenticate("ala@example.org", PASSWORD))
        self.assertIsNotNone(self.store.authenticate("ala@example.org", NEW_PASSWORD))
        self.assertIsNone(self.store.session_user(session))

    def test_newer_token_replaces_older_one(self):
        self.register()
        first = self.store.issue_token("ala@example.org", "reset", NEW_PASSWORD)
        second = self.store.issue_token("ala@example.org", "reset", "third long password")
        self.assertIsNone(self.store.confirm(first))
        self.assertIsNotNone(self.store.confirm(second))

    def test_reset_and_reregistration_do_not_apply_to_wrong_accounts(self):
        self.assertIsNone(self.store.issue_token("nobody@example.org", "reset", NEW_PASSWORD))
        self.register()
        self.assertIsNone(self.store.issue_token("ala@example.org", "register", NEW_PASSWORD))

    def test_sessions_expire_and_can_be_deleted(self):
        user = self.register()
        session = self.store.create_session(user["id"])
        self.assertEqual(self.store.session_user(session)["email"], "ala@example.org")
        self.store.delete_session(session)
        self.assertIsNone(self.store.session_user(session))
        session = self.store.create_session(user["id"])
        self.clock.now += auth_store.SESSION_TTL
        self.assertIsNone(self.store.session_user(session))
        self.assertIsNone(self.store.session_user(None))

    def test_tokens_are_stored_only_as_hashes(self):
        token = self.store.issue_token("ala@example.org", "register", PASSWORD)
        self.assertNotIn(token.encode(), self.store.path.read_bytes())
        self.assertNotIn(PASSWORD.encode(), self.store.path.read_bytes())


class AuthRoutesTests(unittest.TestCase):
    def setUp(self):
        isolated_mcp = patch("web_app.mcp", type(server.mcp)("search", host="0.0.0.0"))
        isolated_mcp.start()
        self.addCleanup(isolated_mcp.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.mailer = FakeMailer()
        self.auth = Auth(AuthStore(Path(directory.name) / "auth.db"), self.mailer,
                         allowed_emails=["ala@example.org", " Ola@Example.org "],
                         public_url="http://szukaj.dom/", trusted_hosts=["testserver"])
        self.service = AsyncMock(return_value=json.dumps({"source": "searxng", "results": []}))
        self.client = TestClient(create_app(self.service, allowed_hosts=["testserver"], auth=self.auth))

    def register(self, email="ala@example.org", password=PASSWORD):
        response = self.client.post("/api/auth/register", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 202)
        return self.client.post("/api/auth/confirm", json={"token": self.mailer.token()})

    def test_full_registration_login_search_logout_cycle(self):
        self.assertEqual(self.client.get("/api/auth/me").json(), {"enabled": True, "user": None})
        self.assertEqual(self.client.post("/api/search", json={"query": "test"}).status_code, 401)
        self.service.assert_not_called()

        confirmed = self.register(email=" ALA@example.org ")
        self.assertEqual(confirmed.status_code, 200)
        recipient, purpose, link = self.mailer.sent[0]
        self.assertEqual((recipient, purpose), ("ala@example.org", "register"))
        self.assertTrue(link.startswith("http://szukaj.dom/?confirm="))
        cookie = confirmed.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"], {"email": "ala@example.org"})
        self.assertEqual(self.client.post("/api/search", json={"query": "test"}).status_code, 200)

        self.assertEqual(self.client.post("/api/auth/logout", json={}).status_code, 204)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])
        self.assertEqual(self.client.post("/api/search", json={"query": "test"}).status_code, 401)

        login = self.client.post("/api/auth/login", json={"email": "ala@example.org", "password": PASSWORD})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json(), {"user": {"email": "ala@example.org"}})

    def test_password_reset_requires_link_confirmation(self):
        self.register()
        self.client.cookies.clear()
        response = self.client.post("/api/auth/password-reset",
                                    json={"email": "ala@example.org", "password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.mailer.sent[-1][1], "reset")
        old = {"email": "ala@example.org", "password": PASSWORD}
        new = {"email": "ala@example.org", "password": NEW_PASSWORD}
        self.assertEqual(self.client.post("/api/auth/login", json=new).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json=old).status_code, 200)
        stolen_session = dict(self.client.cookies)

        confirmed = self.client.post("/api/auth/confirm", json={"token": self.mailer.token()})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(self.client.post("/api/auth/login", json=old).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json=new).status_code, 200)
        self.client.cookies.clear()
        self.client.cookies.update(stolen_session)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])

    def test_responses_do_not_reveal_which_accounts_exist(self):
        self.register()
        answers = []
        for path, email in [("/api/auth/register", "stranger@example.org"),
                            ("/api/auth/register", "ala@example.org"),
                            ("/api/auth/password-reset", "nobody@example.org"),
                            ("/api/auth/password-reset", "ola@example.org")]:
            response = self.client.post(path, json={"email": email, "password": NEW_PASSWORD})
            answers.append((response.status_code, response.json()))
        self.assertEqual(len(set(json.dumps(answer) for answer in answers)), 1)
        self.assertEqual(len(self.mailer.sent), 1)

    def test_registration_is_limited_to_allowed_emails(self):
        self.client.post("/api/auth/register", json={"email": "stranger@example.org", "password": PASSWORD})
        self.assertEqual(self.mailer.sent, [])
        self.assertEqual(self.register(email="ola@example.org").status_code, 200)

    def test_invalid_input_and_tokens_are_rejected(self):
        for body in [{}, {"email": "no-at-sign", "password": PASSWORD}, {"email": "a@b.pl", "password": "short"},
                     {"email": "a@b.pl", "password": "x" * 257}, {"email": ["a@b.pl"], "password": PASSWORD}]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/auth/login", json=body).status_code, 400)
        for token in ["", "nope", 123, "x" * 129]:
            with self.subTest(token=token):
                self.assertEqual(self.client.post("/api/auth/confirm", json={"token": token}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "ala@example.org", "password": PASSWORD})
                         .status_code, 401)

    def test_cross_site_and_non_json_requests_are_rejected(self):
        body = {"email": "ala@example.org", "password": PASSWORD}
        self.assertEqual(self.client.post("/api/auth/login", data=body).status_code, 415)
        for path in ("/api/auth/login", "/api/auth/register", "/api/auth/password-reset",
                     "/api/auth/confirm", "/api/auth/logout"):
            with self.subTest(path=path):
                response = self.client.post(path, json=body, headers={"Origin": "https://evil.example"})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.mailer.sent, [])

    def test_failed_logins_and_emails_are_rate_limited(self):
        wrong = {"email": "ala@example.org", "password": "wrong password!"}
        codes = [self.client.post("/api/auth/login", json=wrong).status_code for _ in range(11)]
        self.assertEqual(codes, [401] * 10 + [429])
        reset = {"email": "ala@example.org", "password": NEW_PASSWORD}
        codes = [self.client.post("/api/auth/password-reset", json=reset).status_code for _ in range(4)]
        self.assertEqual(codes, [202, 202, 202, 429])

    def test_missing_smtp_fails_before_touching_accounts(self):
        self.mailer.available = False
        response = self.client.post("/api/auth/register", json={"email": "ala@example.org", "password": PASSWORD})
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(self.auth.store.find_user("ala@example.org"))

    def test_https_public_url_marks_cookie_secure(self):
        self.auth.public_url, self.auth.secure_cookie = "https://szukaj.dom", True
        self.assertIn("secure", self.register().headers["set-cookie"].lower())

    def test_disabled_auth_keeps_search_open(self):
        with patch.dict("os.environ", {}, clear=True):
            client = TestClient(create_app(self.service, allowed_hosts=["testserver"]))
        self.assertEqual(client.get("/api/auth/me").json(), {"enabled": False, "user": None})
        self.assertEqual(client.post("/api/search", json={"query": "test"}).status_code, 200)
        self.assertEqual(client.post("/api/auth/login", json={}).status_code, 404)

    def test_enabled_from_environment_uses_database_path(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"AUTH_ENABLED": "true", "AUTH_DB_PATH": str(Path(directory) / "env.db"), "APP_ENV": "dev"}
            with patch.dict("os.environ", env, clear=True):
                client = TestClient(create_app(self.service, allowed_hosts=["testserver"]))
            self.assertEqual(client.get("/api/auth/me").json(), {"enabled": True, "user": None})
            self.assertTrue((Path(directory) / "env.db").is_file())


class AuthHelpersTests(unittest.IsolatedAsyncioTestCase):
    def test_email_normalization(self):
        self.assertEqual(normalize_email("  Ala@Example.ORG "), "ala@example.org")
        for bad in (None, 5, "", "ala", "ala@host", "a b@c.pl", "a@" + "x" * 260 + ".pl"):
            self.assertIsNone(normalize_email(bad))

    def test_rate_limiter_window_slides(self):
        clock = Clock()
        limiter = RateLimiter(2, 10, clock=clock)
        self.assertEqual([limiter.allow("k") for _ in range(3)], [True, True, False])
        clock.now += 10
        self.assertTrue(limiter.allow("k"))

    def test_message_contains_link_and_ignore_notice(self):
        message = compose_message("from@example.org", "to@example.org", "reset", "http://szukaj.dom/?confirm=abc")
        body = message.get_content()
        self.assertIn("http://szukaj.dom/?confirm=abc", body)
        self.assertIn("zignoruj", body)
        self.assertEqual(message["To"], "to@example.org")

    async def test_mailer_without_smtp_logs_only_in_dev(self):
        import logging
        previous_disable = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, previous_disable)
        dev = SmtpMailer(host="", app_env="dev")
        self.assertTrue(dev.available)
        with self.assertLogs("szukaj", level="WARNING") as logs:
            await dev.send_link("to@example.org", "register", "http://x/?confirm=abc")
        self.assertIn("confirm=abc", "\n".join(logs.output))
        prod = SmtpMailer(host="", app_env="prod")
        self.assertFalse(prod.available)


if __name__ == "__main__":
    unittest.main()
