import unittest

from lifetxt.collaboration import resolve_membership, require_workspace_permission
from lifetxt.config_validation import validate_config
from lifetxt.remote_access import RemoteAccessError, principal_registry


def _config(members, workspaces=None):
    return {
        "remote": {
            "principals": [
                {"id": "alice", "role": "reader", "scopes": ["write", "admin"]},
                {"id": "bob", "role": "reader", "scopes": ["write"]},
                {"id": "disabled", "role": "reader", "disabled": True},
            ]
        },
        "default_workspace": "team",
        "workspaces": workspaces
        or {
            "team": {
                "sources": ["team.life.txt"],
                "collaboration": {"members": members},
            }
        },
    }


class CollaborationResolverTests(unittest.TestCase):
    def test_owner_editor_viewer_and_nonmember_permissions(self):
        config = _config(
            {
                "alice": {"role": "owner"},
                "bob": {"role": "editor"},
                "disabled": {"role": "viewer"},
            }
        )
        alice = resolve_membership(config, principal_registry(config)["alice"])
        bob = resolve_membership(config, principal_registry(config)["bob"])
        self.assertEqual(alice["role"], "owner")
        self.assertEqual(
            alice["permissions"], {"read": True, "write": True, "member_admin": True}
        )
        self.assertEqual(
            bob["permissions"], {"read": True, "write": True, "member_admin": False}
        )
        with self.assertRaises(RemoteAccessError):
            resolve_membership(
                config, {"id": "carol", "scopes": ["read", "write", "admin"]}
            )
        with self.assertRaises(RemoteAccessError):
            resolve_membership(config, principal_registry(config)["disabled"])

    def test_role_never_widens_principal_scopes(self):
        config = _config({"alice": {"role": "owner"}})
        principal = dict(principal_registry(config)["alice"])
        principal["scopes"] = ["read"]
        result = resolve_membership(config, principal)
        self.assertEqual(
            result["permissions"], {"read": True, "write": False, "member_admin": False}
        )
        with self.assertRaises(RemoteAccessError):
            require_workspace_permission(config, principal, "write")

    def test_membership_isolated_per_workspace(self):
        config = _config(
            {},
            {
                "A": {
                    "sources": ["a.txt"],
                    "collaboration": {"members": {"alice": {"role": "owner"}}},
                },
                "B": {
                    "sources": ["b.txt"],
                    "collaboration": {"members": {"alice": {"role": "viewer"}}},
                },
                "C": {
                    "sources": ["c.txt"],
                    "collaboration": {"members": {"bob": {"role": "owner"}}},
                },
            },
        )
        alice = principal_registry(config)["alice"]
        self.assertEqual(resolve_membership(config, alice, "A")["role"], "owner")
        self.assertEqual(resolve_membership(config, alice, "B")["role"], "viewer")
        with self.assertRaises(RemoteAccessError):
            resolve_membership(config, alice, "C")

    def test_legacy_config_preserves_scope_permissions(self):
        result = resolve_membership(
            {}, {"id": "local", "scopes": ["read", "write", "admin"]}
        )
        self.assertFalse(result["collaboration_enabled"])
        self.assertEqual(
            result["permissions"], {"read": True, "write": True, "member_admin": False}
        )

    def test_invalid_membership_fails_config_validation(self):
        cases = [
            _config({"alice": {"role": "administrator"}}),
            _config({"carol": {"role": "owner"}}),
            _config({"disabled": {"role": "owner"}}),
        ]
        for config in cases:
            with self.subTest(config=config):
                self.assertTrue(
                    any(
                        row["code"] in ("C021", "C022", "C023")
                        for row in validate_config(config, use_jsonschema=False)
                    )
                )


if __name__ == "__main__":
    unittest.main()
