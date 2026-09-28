import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import cli
from lifetxt.remote_client import (
    PROFILE_VERSION,
    _load,
    change_workspace_member,
    get_profile,
    request,
    set_profile,
    workspace_members,
)


class FakeResponse(object):
    def __init__(self, value, version="2"):
        self.value = value
        self.headers = {
            "X-Lifetxt-Remote-Version": version,
            "X-Lifetxt-Remote-Capability-Revision": "a" * 64,
        }

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
                json.dump(
                    {
                        "version": 2,
                        "profiles": {
                            "home": {
                                "url": "https://example.test",
                                "token_env": "TOKEN",
                            }
                        },
                    },
                    handle,
                )
            data = _load(path)
            self.assertEqual(PROFILE_VERSION, data["version"])
            self.assertEqual(2, data["profiles"]["home"]["protocol_version"])
            self.assertTrue(data["profiles"]["home"]["verify_tls"])

    @mock.patch("lifetxt.remote_client.urlopen")
    def test_request_sends_and_validates_protocol_header(self, opener):
        opener.return_value = FakeResponse({"ok": True})
        value, headers = request(
            {"url": "https://example.test", "protocol_version": 2},
            "GET",
            "/api/remote/v1/diagnostics",
        )
        self.assertTrue(value["ok"])
        sent = opener.call_args[0][0]
        self.assertEqual("2", sent.headers["X-lifetxt-remote-version"])
        self.assertEqual(2, headers["lifetxt_negotiated_protocol"])

    @mock.patch("lifetxt.remote_client.urlopen")
    def test_protocol_mismatch_is_rejected(self, opener):
        opener.return_value = FakeResponse({"ok": True}, version="1")
        with self.assertRaises(RuntimeError):
            request(
                {"url": "https://example.test", "protocol_version": 2},
                "GET",
                "/api/remote/v1/session",
            )

    def test_profile_and_cli_include_protocol_and_resource_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "profiles.json")
            set_profile(
                "home", "https://example.test", "TOKEN", protocol_version=2, path=path
            )
            self.assertEqual(2, get_profile("home", path)["protocol_version"])
        parser = cli.build_parser()
        args = parser.parse_args(
            ["remote", "get", "home", "items", "--param", "q=test"]
        )
        self.assertEqual("items", args.resource)
        args = parser.parse_args(["remote", "profile-remove", "home"])
        self.assertEqual("home", args.name)
        args = parser.parse_args(
            [
                "remote",
                "member-role",
                "home",
                "--workspace",
                "team",
                "--principal",
                "bob",
                "--role",
                "viewer",
                "--config-revision",
                "a" * 64,
            ]
        )
        self.assertEqual("role", args.operation)

    @mock.patch("lifetxt.remote_client.urlopen")
    def test_member_cli_calls_only_the_authoritative_remote_api(self, opener):
        opener.return_value = FakeResponse({"members": [], "config_revision": "a" * 64})
        profile = {"url": "https://example.test", "protocol_version": 2}
        listing = workspace_members(profile, "team")
        self.assertEqual("a" * 64, listing["config_revision"])
        self.assertIn("workspace=team", opener.call_args[0][0].full_url)

        opener.return_value = FakeResponse({"ok": True})
        changed = change_workspace_member(
            profile, "team", "add", "bob", "editor", "a" * 64
        )
        self.assertTrue(changed["ok"])
        sent = opener.call_args[0][0]
        self.assertEqual("POST", sent.method)
        self.assertEqual(
            "/api/remote/v1/workspace/members",
            sent.full_url.split("?", 1)[0].replace("https://example.test", ""),
        )
        self.assertEqual(
            {
                "workspace": "team",
                "operation": "add",
                "principal_id": "bob",
                "role": "editor",
                "expected_config_revision": "a" * 64,
            },
            json.loads(sent.data.decode("utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
