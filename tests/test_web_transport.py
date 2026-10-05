"""Browser origin contracts independent of optional Web packages."""

import unittest
from types import SimpleNamespace

from lifetxt.web_transport import expected_origin, origin_parts


class Headers:
    def __init__(self, values):
        self.values = [(k.lower(), v) for k, v in values]

    def getlist(self, key):
        return [v for k, v in self.values if k == key]

    def get(self, key, default=None):
        return next(iter(self.getlist(key)), default)


class WebTransportTests(unittest.TestCase):
    def request(self, values=(), peer="127.0.0.1"):
        return SimpleNamespace(
            headers=Headers(values),
            client=SimpleNamespace(host=peer) if peer else None,
            url=SimpleNamespace(scheme="http", netloc="life.example.test"),
        )

    def test_default_ports_ipv6_and_origin_validation(self):
        self.assertEqual(
            origin_parts("https://EXAMPLE.test:443"),
            origin_parts("https://example.test"),
        )
        self.assertEqual(("http", "::1", 8000), origin_parts("http://[::1]:8000"))
        for value in (
            "null",
            "https://x/",
            "https://user@x",
            "https://x?",
            "https://x#",
            "https://x:bad",
            "https://x:0",
            "https://x:",
            "https://x:99999",
            "https://x,http://x",
            "https://x\\evil",
            "https://x\n",
            "https://[bad]",
        ):
            with self.subTest(value=value):
                self.assertIsNone(origin_parts(value))

    def test_untrusted_headers_and_forwarded_standard_are_ignored(self):
        request = self.request(
            [
                ("Host", "life.example.test"),
                ("X-Forwarded-Proto", "https"),
                ("X-Forwarded-Host", "attacker.test"),
                ("Forwarded", "proto=https;host=attacker.test"),
            ]
        )
        self.assertEqual("http://life.example.test", expected_origin(request, {}))
        self.assertEqual(
            "http://life.example.test",
            expected_origin(request, {"remote": {"trusted_proxies": ["192.0.2.1/32"]}}),
        )

    def test_trusted_proxy_single_values_and_ambiguous_refusal(self):
        config = {"remote": {"trusted_proxies": ["127.0.0.1/32"]}}
        values = [("X-Forwarded-Proto", "https"), ("X-Forwarded-Host", "[::1]:8443")]
        self.assertEqual(
            "https://[::1]:8443", expected_origin(self.request(values), config)
        )
        for extra in (
            [("X-Forwarded-Proto", "https,http")],
            [("X-Forwarded-Host", "x,y")],
            [("X-Forwarded-Host", "")],
            [("X-Forwarded-Host", "user@x")],
            [("X-Forwarded-Proto", "ftp")],
            [("Host", "x"), ("Host", "y")],
        ):
            with self.subTest(extra=extra):
                self.assertIsNone(expected_origin(self.request(values + extra), config))
        self.assertEqual(
            "http://life.example.test",
            expected_origin(self.request(values, peer=None), config),
        )
