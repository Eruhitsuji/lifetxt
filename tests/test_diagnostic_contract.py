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
    def _cli_env(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = os.pathsep.join(
            [ROOT_DIR] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        return env

    def _cli_check_stdin(self, line):
        with tempfile.TemporaryDirectory(prefix="lifetxt-contract-cli-") as cwd:
            process = subprocess.Popen(
                [sys.executable, "-m", "lifetxt", "check", "-", "--format", "json"],
                cwd=cwd,
                env=self._cli_env(),
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

    def _cli_check_paths(self, paths):
        with tempfile.TemporaryDirectory(prefix="lifetxt-contract-cli-") as cwd:
            process = subprocess.Popen(
                [sys.executable, "-m", "lifetxt", "check"]
                + list(paths)
                + ["--format", "json"],
                cwd=cwd,
                env=self._cli_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate()
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

    @unittest.skipIf(TestClient is None, "web extras unavailable")
    def test_cli_web_and_mcp_share_source_diagnostic_contract(self):
        from lifetxt.webapp import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = os.path.join(temp_dir, "first.life.txt")
            second_path = os.path.join(temp_dir, "second.life.txt")
            with open(first_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Good id:good\n")
            with open(second_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[X] T Bad_status\n")

            expected = [
                {
                    "severity": "error",
                    "code": "E003",
                    "category": "syntax",
                    "message": "Invalid status '[X]'.",
                    "source": second_path,
                    "line": 1,
                    "column": 1,
                    "hint": "",
                },
            ]
            cli_diagnostics, cli_stderr, cli_code = self._cli_check_paths(
                [first_path, second_path]
            )
            client = TestClient(
                create_app(paths=[first_path, second_path], writable_path=first_path)
            )
            web_diagnostics = client.get("/api/items").json()["diagnostics"]
            context = McpContext(paths=[first_path, second_path], writable_path=first_path)
            mcp_diagnostics = call_tool("list_items", {}, context)["diagnostics"]

            self.assertEqual("", cli_stderr)
            self.assertEqual(1, cli_code)
            self.assertEqual(expected, cli_diagnostics)
            self.assertEqual(expected, web_diagnostics)
            self.assertEqual(expected, mcp_diagnostics)

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
