from __future__ import unicode_literals

import json
import os
import subprocess
import sys
import tempfile
import unittest

from lifetxt.diagnostic_contract import diagnostic_to_output_dict
from lifetxt.mcp import McpContext, call_tool
from lifetxt.model import Diagnostic
from tests.diagnostic_contract_fixtures import DIAGNOSTIC_CONTRACT_FIXTURES

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DiagnosticContractTests(unittest.TestCase):
    def _cli_check_stdin(self, line):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = os.pathsep.join(
            [ROOT_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        with tempfile.TemporaryDirectory(prefix="lifetxt-contract-cli-") as cwd:
            process = subprocess.Popen(
                [sys.executable, "-m", "lifetxt", "check", "-", "--format", "json"],
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate((line + "\n").encode("utf-8"))
        return (
            json.loads(stdout.decode("utf-8")),
            stderr.decode("utf-8"),
            process.returncode,
        )

    def _mcp_check_line(self, line):
        context = McpContext(paths=[])
        return call_tool("check_line", {"line": line}, context)["diagnostics"]

    @unittest.skipIf(TestClient is None, "web extras unavailable")
    def test_cli_web_and_mcp_share_check_line_diagnostic_contract(self):
        from lifetxt.webapp import create_app

        client = TestClient(create_app(paths=[]))
        for case in DIAGNOSTIC_CONTRACT_FIXTURES:
            cli_diagnostics, cli_stderr, cli_code = self._cli_check_stdin(case["line"])
            web_diagnostics = client.post(
                "/api/check-line",
                json={"line": case["line"]},
            ).json()["diagnostics"]
            mcp_diagnostics = self._mcp_check_line(case["line"])

            self.assertEqual("", cli_stderr, case["name"])
            self.assertEqual(case["exit_code"], cli_code, case["name"])
            self.assertEqual(case["diagnostics"], cli_diagnostics, case["name"])
            self.assertEqual(case["diagnostics"], web_diagnostics, case["name"])
            self.assertEqual(case["diagnostics"], mcp_diagnostics, case["name"])

    def test_absent_hint_is_empty_string(self):
        row = Diagnostic("warning", "W999", "No hint.").to_dict()
        self.assertIn("hint", row)
        self.assertEqual("", row["hint"])

    def test_contract_builder_publishes_category_and_hint(self):
        diagnostic = Diagnostic("warning", "W226", "Bad duration.", line=7)
        self.assertEqual(
            {
                "severity": "warning",
                "code": "W226",
                "category": "duration",
                "message": "Bad duration.",
                "line": 7,
                "hint": "",
            },
            diagnostic_to_output_dict(diagnostic),
        )
