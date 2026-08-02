import os, tempfile, unittest
from unittest import mock
from lifetxt.remote_client import *


class RemoteClientTests(unittest.TestCase):
    def test_profiles_store_token_env_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "profiles.json")
            set_profile("home", "https://example.test", "LIFETXT_TOKEN", path=p)
            self.assertEqual(get_profile("home", p)["token_env"], "LIFETXT_TOKEN")
            self.assertNotIn("secret", open(p).read())
            self.assertTrue(delete_profile("home", p))

    def test_non_loopback_http_rejected(self):
        with self.assertRaises(ValueError):
            set_profile("bad", "http://example.test")

    def test_loopback_http_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(
                set_profile(
                    "dev", "http://127.0.0.1:8000", path=os.path.join(d, "p.json")
                )
            )

    def test_render(self):
        text = render_tui(
            {
                "revision": "abc",
                "tickets": [{"id": "T-1", "title": "Fix"}],
                "projects": [],
            }
        )
        self.assertIn("T-1", text)

    @mock.patch("lifetxt.remote_client.request")
    def test_connection(self, req):
        req.side_effect = [({"enabled": True}, {}), ({"principal": {"id": "a"}}, {})]
        self.assertTrue(test_connection({"url": "https://x"})["ok"])
