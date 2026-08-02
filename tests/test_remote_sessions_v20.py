import unittest

from lifetxt.remote_access import RemoteAccessError
from lifetxt.remote_sessions import (
    BrowserSessionStore,
    cookie_name,
    require_csrf,
    session_payload,
    validate_session_configuration,
)


class FakeClock(object):
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class RemoteBrowserSessionTests(unittest.TestCase):
    def principal(self, principal_id="alice"):
        return {
            "id": principal_id,
            "display_name": principal_id.title(),
            "role": "editor",
            "scopes": ["read", "write"],
            "projects": ["web"],
            "groups": [],
            "visibilities": ["public", "shared"],
            "disabled": False,
            "token_env": "SECRET_ENV",
        }

    def config(self, **remote):
        value = {
            "enabled": True,
            "browser_ui": True,
            "browser_session_ttl_seconds": 120,
            "browser_session_idle_seconds": 30,
            "browser_session_max": 2,
        }
        value.update(remote)
        return {"remote": value}

    def test_session_is_opaque_and_public_payload_hides_token_env(self):
        tokens = iter(("session-1", "csrf-1"))
        store = BrowserSessionStore(token_factory=lambda _size: next(tokens))
        row = store.create(self.principal(), "browser-session", self.config())
        self.assertEqual("session-1", row["session_id"])
        payload = session_payload(row)
        self.assertEqual("csrf-1", payload["csrf_token"])
        self.assertNotIn("token_env", payload["principal"])
        self.assertTrue(payload["restart_invalidates_session"])

    def test_idle_and_absolute_expiry(self):
        clock = FakeClock()
        tokens = iter(("session-1", "csrf-1"))
        store = BrowserSessionStore(
            clock=clock, token_factory=lambda _size: next(tokens)
        )
        row = store.create(self.principal(), "browser-session", self.config())
        clock.advance(20)
        self.assertEqual(
            "alice", store.resolve(row["session_id"], self.config())["principal"]["id"]
        )
        clock.advance(31)
        with self.assertRaises(RemoteAccessError) as caught:
            store.resolve(row["session_id"], self.config())
        self.assertEqual("SESSION_EXPIRED", caught.exception.code)

    def test_oldest_session_is_evicted_at_capacity(self):
        tokens = iter(("s1", "c1", "s2", "c2", "s3", "c3"))
        store = BrowserSessionStore(token_factory=lambda _size: next(tokens))
        config = self.config(browser_session_max=2)
        first = store.create(self.principal("a"), "browser-session", config)
        store.create(self.principal("b"), "browser-session", config)
        store.create(self.principal("c"), "browser-session", config)
        self.assertEqual(2, store.count())
        with self.assertRaises(RemoteAccessError):
            store.resolve(first["session_id"], config)

    def test_csrf_and_exact_origin_are_required(self):
        session = {"csrf_token": "csrf-1"}
        config = self.config(allowed_origins=["https://extra.example"])
        require_csrf(
            session,
            {"X-CSRF-Token": "csrf-1"},
            "POST",
            "https://life.example",
            "https://life.example",
            config,
        )
        require_csrf(
            session,
            {"X-CSRF-Token": "csrf-1"},
            "POST",
            "https://extra.example",
            "https://life.example",
            config,
        )
        with self.assertRaises(RemoteAccessError) as caught:
            require_csrf(
                session,
                {},
                "POST",
                "https://life.example",
                "https://life.example",
                config,
            )
        self.assertEqual("CSRF_REQUIRED", caught.exception.code)
        with self.assertRaises(RemoteAccessError) as caught:
            require_csrf(
                session,
                {"X-CSRF-Token": "csrf-1"},
                "POST",
                "https://evil.example",
                "https://life.example",
                config,
            )
        self.assertEqual("ORIGIN_FORBIDDEN", caught.exception.code)

    def test_invalid_cookie_header_and_origin_configuration_fail_closed(self):
        with self.assertRaises(RemoteAccessError) as caught:
            cookie_name(self.config(session_cookie_name="bad cookie"))
        self.assertEqual("REMOTE_SESSION_CONFIG_INVALID", caught.exception.code)
        with self.assertRaises(RemoteAccessError):
            validate_session_configuration(self.config(csrf_header="Bad Header"))
        with self.assertRaises(RemoteAccessError):
            validate_session_configuration(
                self.config(allowed_origins=["https://example.test/path"])
            )


if __name__ == "__main__":
    unittest.main()
