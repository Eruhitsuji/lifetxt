import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.check_branch_readiness import inspect, main, valid_branch_name


ROOT = Path(__file__).resolve().parent.parent
SOURCES = (
    ".ai/project/BRANCH_STRATEGY.json",
    ".ai/project/PROJECT.yml",
    ".ai/project/MERGE_POLICY.yml",
    ".ai/project/RULES.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "lifetxt/server_update.py",
    "docs/deployment/ubuntu-server.md",
)


class BranchReadinessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in SOURCES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_current_repository_and_fixture_remain_deferred(self):
        for root in (ROOT, self.root):
            report = inspect(root)
            self.assertTrue(report["current_contract_ok"], report["errors"])
            self.assertFalse(report["migration_ready"])
            self.assertEqual(
                {"branch": "next", "state": "deferred"}, report["candidate"]
            )
            self.assertEqual(
                {"change_required", "manual_required"},
                {check["status"] for check in report["checks"]},
            )

    def test_candidate_override_and_json_output_are_read_only(self):
        before = {name: (self.root / name).read_bytes() for name in SOURCES}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                ["--root", str(self.root), "--candidate", "staging/next", "--json"]
            )
        self.assertEqual(0, code)
        report = json.loads(output.getvalue())
        self.assertEqual("staging/next", report["candidate"]["branch"])
        self.assertFalse(report["migration_ready"])
        self.assertEqual(
            before, {name: (self.root / name).read_bytes() for name in SOURCES}
        )
        self.assertEqual(len(SOURCES), sum(p.is_file() for p in self.root.rglob("*")))

    def test_invalid_candidate_names_and_current_alias_are_rejected(self):
        for name in (
            "",
            "../next",
            "next..v1",
            "next.lock",
            "-next",
            "a//b",
            "next/",
            "next.",
            "a/.hidden",
            "a b",
            "$(touch x)",
            "@",
            "main",
        ):
            with self.subTest(name=name):
                self.assertFalse(inspect(self.root, name)["current_contract_ok"])
        for name in ("next", "staging/next", "next-v1", "next_v1"):
            self.assertTrue(valid_branch_name(name))

    def test_invalid_strategy_is_not_success(self):
        path = self.root / SOURCES[0]
        original = json.loads(path.read_text())
        for update in (
            {"schema_version": 2},
            {"mode": "next"},
            {"roles": {}},
            {"roles": {"integration": "next", "release": "main", "deployment": "main"}},
            {"future": {"candidate": "next", "state": "active"}},
        ):
            with self.subTest(update=update):
                path.write_text(json.dumps(dict(original, **update)))
                self.assertFalse(inspect(self.root)["current_contract_ok"])
        for malformed in (
            "{",
            "null",
            "[]",
            '{"schema_version": 1, "schema_version": 2}',
        ):
            path.write_text(malformed)
            self.assertFalse(inspect(self.root)["current_contract_ok"])

    def test_source_contradictions_and_missing_files_fail(self):
        for name, old, new in (
            (".ai/project/PROJECT.yml", "default_branch: main", "default_branch: next"),
            (
                ".ai/project/MERGE_POLICY.yml",
                "default_branch: main",
                "default_branch: next",
            ),
            (".ai/project/RULES.md", "`base=main`", "`base=next`"),
            (".github/workflows/ci.yml", "      - main", "      - next"),
            (".github/workflows/ci.yml", "      - main", "      - main\n      - next"),
            (".github/workflows/release.yml", '"v*.*.*"', '"next-*"'),
            ("lifetxt/server_update.py", '"--ff-only"', '"--squash"'),
            ("docs/deployment/ubuntu-server.md", '"ref": "main"', '"ref": "next"'),
        ):
            path = self.root / name
            original = path.read_text()
            with self.subTest(name=name):
                self.assertIn(old, original)
                path.write_text(original.replace(old, new))
                self.assertFalse(inspect(self.root)["current_contract_ok"])
                path.write_text(original)
        (self.root / ".ai/project/MERGE_POLICY.yml").unlink()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(1, main(["--root", str(self.root), "--json"]))
        self.assertTrue(json.loads(output.getvalue())["errors"])


if __name__ == "__main__":
    unittest.main()
