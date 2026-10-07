"""Regression tests for plot date-bound validation (#1136)."""

import os
import tempfile

from lifetxt import entrypoint
from tests.test_core_cli_entrypoint import CliContractTestCase


class PlotCliRangeValidationTests(CliContractTestCase):
    def _make_file(self, text):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        handle.write(text)
        handle.flush()
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def _run(self, *argv):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        code = entrypoint.main(list(argv))
        return code, self.stdout.getvalue(), self.stderr.getvalue()

    def test_invalid_explicit_bounds_fail_before_chart_processing(self):
        sources = ("", "[x] T Done done:2026-06-10\n")
        bounds = (
            ("--from", "Invalid --from 'bad'."),
            ("--to", "Invalid --to 'bad'."),
        )
        for source in sources:
            path = self._make_file(source)
            for option, message in bounds:
                with self.subTest(source=bool(source), option=option):
                    code, out, err = self._run(
                        "plot",
                        path,
                        "--chart",
                        "tasks",
                        option,
                        "bad",
                    )
                    self.assertEqual(1, code)
                    self.assertEqual("", out)
                    self.assertEqual("ERROR: " + message + "\n", err)
                    self.assertNotIn("Traceback", err)
