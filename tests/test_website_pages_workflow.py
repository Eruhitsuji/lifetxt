"""Publication trust-boundary regressions for #1352; never deploy anything."""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(yaml is None, "Optional PyYAML unavailable")
class WebsitePagesWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(
            (ROOT / ".github/workflows/website-pages.yml").read_text(encoding="utf-8")
        )
        self.build = self.workflow["jobs"]["build"]
        self.deploy = self.workflow["jobs"]["deploy"]
        guards = [
            step for step in self.build["steps"] if "protection" in step.get("name", "")
        ]
        command = guards[0]["run"]
        self.guard = command.split("\n", 1)[1].rsplit("\nPY", 1)[0]
        self.env = {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "Eruhitsuji/lifetxt",
        }
        self.protection = {
            "name": "github-pages",
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [
                        {
                            "type": "User",
                            "reviewer": {"type": "User", "login": "Eruhitsuji"},
                        }
                    ],
                }
            ],
        }

    def execute_guard(self, payload):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch(
                "urllib.request.urlopen", return_value=io.BytesIO(payload)
            ) as request,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exec(compile(self.guard, "workflow-human-protection", "exec"), {})
        return request

    def test_only_manual_official_main_can_upload_or_deploy(self):
        events = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(events), {"pull_request", "workflow_dispatch"})
        for step in self.build["steps"]:
            if step.get("uses", "").startswith("actions/upload-pages-artifact@"):
                condition = step["if"]
                self.assertIn("workflow_dispatch", condition)
                self.assertIn("refs/heads/main", condition)
                self.assertIn("Eruhitsuji/lifetxt", condition)
                self.assertEqual(step["with"]["path"], ".cache/pages")
        self.assertIn("workflow_dispatch", self.deploy["if"])
        self.assertIn("refs/heads/main", self.deploy["if"])
        self.assertIn("Eruhitsuji/lifetxt", self.deploy["if"])
        self.assertEqual(self.deploy["needs"], "build")
        self.assertEqual(self.deploy["environment"]["name"], "github-pages")
        self.assertEqual(self.build["permissions"], {"contents": "read"})
        self.assertEqual(
            self.deploy["permissions"], {"pages": "write", "id-token": "write"}
        )
        self.assertNotIn("pull_request_target", events)
        for job in (self.build, self.deploy):
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^actions/[a-z-]+@[0-9a-f]{40}$")
                    self.assertNotIn("configure-pages", step["uses"])
        # The privileged job never executes PR/checkout scripts.
        self.assertFalse(
            any("checkout" in step.get("uses", "") for step in self.deploy["steps"])
        )
        second = self.deploy["steps"][0]["run"].split("\n", 1)[1].rsplit("\nPY", 1)[0]
        self.assertEqual(self.guard, second)
        self.assertFalse(re.search(r"\$\{\{.*\}\}", self.guard))

    def test_guard_reads_only_public_environment_and_accepts_human_gate(self):
        request = self.execute_guard(json.dumps(self.protection).encode())
        args, kwargs = request.call_args
        self.assertEqual(
            args[0].full_url,
            "https://api.github.com/repos/Eruhitsuji/lifetxt/environments/github-pages",
        )
        self.assertEqual(args[0].get_method(), "GET")
        self.assertNotIn("Authorization", args[0].headers)
        self.assertEqual(kwargs["timeout"], 15)

    def test_unprotected_malformed_and_bot_reviewers_fail_closed(self):
        cases = [b"not json", b"{}", b'{"name":"github-pages","protection_rules":[]}']
        for reviewer in (
            {"type": "User", "reviewer": {"type": "Bot", "login": "Eruhitsuji"}},
            {"type": "User", "reviewer": {"type": "User", "login": "someone-else"}},
            {"type": "Team", "reviewer": {"type": "User", "login": "Eruhitsuji"}},
        ):
            cases.append(
                json.dumps(
                    {
                        "name": "github-pages",
                        "protection_rules": [
                            {"type": "required_reviewers", "reviewers": [reviewer]}
                        ],
                    }
                ).encode()
            )
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(SystemExit):
                self.execute_guard(payload)
        with patch("urllib.request.urlopen", side_effect=OSError("API unavailable")):
            with (
                patch.dict(os.environ, self.env, clear=True),
                self.assertRaises(SystemExit),
            ):
                exec(compile(self.guard, "guard", "exec"), {})

    def test_pr_fork_and_non_main_never_even_query_environment(self):
        for key, value in (
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/feature/test"),
            ("GITHUB_REF", "refs/tags/main"),
            ("GITHUB_REPOSITORY", "someone/lifetxt"),
        ):
            with self.subTest(key=key, value=value):
                self.env[key] = value
                with self.assertRaises(SystemExit):
                    self.execute_guard(json.dumps(self.protection).encode())
                self.env = {
                    "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "GITHUB_REF": "refs/heads/main",
                    "GITHUB_REPOSITORY": "Eruhitsuji/lifetxt",
                }
