import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import cli
from lifetxt.remote_client import (
    PROFILE_VERSION,
    _load,
    get_profile,
    request,
    set_profile,
)


class FakeResponse(object):
    def __init__(self, value, version="2"):
        self.value = value
        self.headers = {"X-Lifetxt-Remote-Version": version, "X-Lifetxt-Remote-Capability-Revision": "a" * 64}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


class RemoteClientV20Tests(unittest.TestCase):
    def test_v2_profile_is_migrated_in_memory_to_v3(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "profiles.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"version": 2, "profiles": {"home": {"url": "https://example.test", "token_env": "TOKEN"}}}, handle)
            data = _load(path)
            self.assertEqual(PROFILE_VERSION, data["version"])
            self.assertEqual(2, data["profiles"]["home"]["protocol_version"])
            self.assertTrue(data["profiles"]["home"]["verify_tls"])

    @mock.patch("lifetxt.remote_client.urlopen")
    def test_request_sends_and_validates_protocol_header(self, opener):
        opener.return_value = FakeResponse({"ok": True})
        value, headers = request({"url": "https://example.test", "protocol_version": 2}, "GET", "/api/remote/v1/diagnostics")
        self.assertTrue(value["ok"])
        sent = opener.call_args.args[0]
        self.assertEqual("2", sent.headers["X-lifetxt-remote-version"])
        self.assertEqual(2, headers["lifetxt_negotiated_protocol"])

    @mock.patch("lifetxt.remote_client.urlopen")
    def test_protocol_mismatch_is_rejected(self, opener):
        opener.return_value = FakeResponse({"ok": True}, version="1")
        with self.assertRaises(RuntimeError):
            request({"url": "https://example.test", "protocol_version": 2}, "GET", "/api/remote/v1/session")

    def test_profile_and_cli_include_protocol_and_resource_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "profiles.json")
            set_profile("home", "https://example.test", "TOKEN", protocol_version=2, path=path)
            self.assertEqual(2, get_profile("home", path)["protocol_version"])
        parser = cli.build_parser()
        args = parser.parse_args(["remote", "get", "home", "items", "--param", "q=test"])
        self.assertEqual("items", args.resource)
        args = parser.parse_args(["remote", "profile-remove", "home"])
        self.assertEqual("home", args.name)


if __name__ == "__main__":
    unittest.main()
