"""Tests for `lifetxt/cli_taxonomy.py`: the role-based `--help` categories,
progressive-disclosure `lifetxt help`, and the machine-readable
`lifetxt help --json` surface (#629).

`cli_taxonomy.all_commands()` is the runtime-derived ground truth (built from
`cli.build_parser()`'s subparser tree plus `entrypoint`'s extended-command
sets, never hand-copied) -- these tests exist specifically to catch a real
command silently missing from the hand-curated `CATEGORIES`/safety metadata
in that module, which is the exact "drift" #629 asks to be able to detect.
"""

import json
import os
import re
import unittest

from lifetxt import cli_taxonomy
from tests.test_lifetxt import run_cli


_CATEGORY_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def _docs_categories(doc_path):
    """Parse docs/en/cli.md's "## 1. Command Categories and Guided Paths"
    table into ``{title: [command, ...]}``, mirroring
    ``cli_taxonomy.CATEGORIES``'s own title/commands shape so the two can be
    compared directly without a second parsing convention."""
    with open(doc_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("### 1.1 Command Categories and Guided Paths")
    end = text.index("Guided paths (", start)
    section = text[start:end]

    categories = {}
    for line in section.splitlines():
        match = _CATEGORY_ROW.match(line.strip())
        if not match:
            continue
        title, cell = match.group(1), match.group(2)
        if title in ("Category", "---"):
            continue
        commands = []
        for token in cell.split(","):
            token = re.sub(r"\([^)]*\)", "", token)  # drop "(add)"-style aliases
            token = token.strip().strip("`").strip()
            if token:
                commands.append(token)
        categories[title] = commands
    return categories


class CategoryCoverageTests(unittest.TestCase):
    """Every real command has exactly one category, and vice versa."""

    def test_every_real_command_is_categorized(self):
        uncategorized = [
            name
            for name in cli_taxonomy.all_commands()
            if cli_taxonomy.command_category(name) is None
        ]
        self.assertEqual(
            [],
            uncategorized,
            "commands missing from cli_taxonomy.CATEGORIES: %s" % uncategorized,
        )

    def test_categories_contain_no_removed_or_renamed_commands(self):
        real = set(cli_taxonomy.all_commands())
        categorized = set()
        for category in cli_taxonomy.CATEGORIES.values():
            categorized.update(category["commands"])
        stale = sorted(categorized - real)
        self.assertEqual(
            [],
            stale,
            "cli_taxonomy.CATEGORIES names commands that no longer exist: %s" % stale,
        )

    def test_no_command_appears_in_more_than_one_category(self):
        seen = {}
        for category_id, category in cli_taxonomy.CATEGORIES.items():
            for name in category["commands"]:
                self.assertNotIn(
                    name,
                    seen,
                    "%r is in both %r and %r" % (name, seen.get(name), category_id),
                )
                seen[name] = category_id

    def test_all_commands_matches_a_direct_parser_walk(self):
        from lifetxt.cli import build_parser
        from lifetxt.entrypoint import _EXTRA_COMMANDS, _PERSONAL_CONTEXT_COMMANDS

        parser = build_parser()
        sub_action = None
        for action in parser._actions:
            if action.__class__.__name__ == "_SubParsersAction":
                sub_action = action
                break
        self.assertIsNotNone(sub_action)
        by_identity = {}
        for name, subparser in sub_action.choices.items():
            by_identity.setdefault(id(subparser), []).append(name)
        canonical = set()
        for names in by_identity.values():
            subparser = sub_action.choices[names[0]]
            prog_last = subparser.prog.rsplit(" ", 1)[-1]
            canonical.add(
                prog_last if prog_last in names else sorted(names, key=len)[-1]
            )
        expected = canonical | set(_EXTRA_COMMANDS) | set(_PERSONAL_CONTEXT_COMMANDS)
        expected |= {"report", "server-report"}
        self.assertEqual(expected, set(cli_taxonomy.all_commands()))


class SafetyMetadataTests(unittest.TestCase):
    def test_write_commands_are_real_commands(self):
        real = set(cli_taxonomy.all_commands())
        self.assertEqual([], sorted(cli_taxonomy.WRITE_COMMANDS - real))

    def test_destructive_commands_are_a_subset_of_write_commands(self):
        self.assertEqual(
            [],
            sorted(cli_taxonomy.DESTRUCTIVE_COMMANDS - cli_taxonomy.WRITE_COMMANDS),
        )

    def test_command_safety_shape(self):
        self.assertEqual(
            {"read_only": True, "destructive": False},
            dict(cli_taxonomy.command_safety("today")),
        )
        self.assertEqual(
            {"read_only": False, "destructive": False},
            dict(cli_taxonomy.command_safety("quick")),
        )
        self.assertEqual(
            {"read_only": False, "destructive": True},
            dict(cli_taxonomy.command_safety("migrate")),
        )


class AliasResolutionTests(unittest.TestCase):
    def test_alias_add_resolves_to_quick(self):
        self.assertEqual(("command", "quick"), cli_taxonomy.resolve_topic("add"))

    def test_canonical_name_resolves_to_itself(self):
        self.assertEqual(("command", "quick"), cli_taxonomy.resolve_topic("quick"))

    def test_audience_id_resolves_as_audience(self):
        self.assertEqual(
            ("audience", "beginner"), cli_taxonomy.resolve_topic("beginner")
        )

    def test_unknown_topic_raises_value_error_naming_audiences(self):
        with self.assertRaises(ValueError) as ctx:
            cli_taxonomy.resolve_topic("not-a-real-command")
        self.assertIn("beginner", str(ctx.exception))

    def test_command_aliases_reports_known_aliases(self):
        self.assertEqual(("q", "add"), cli_taxonomy.command_aliases("quick"))
        self.assertEqual((), cli_taxonomy.command_aliases("today"))


class AudienceAndExampleDataTests(unittest.TestCase):
    def test_every_audience_flow_command_is_real(self):
        real = set(cli_taxonomy.all_commands())
        for audience_id, audience in cli_taxonomy.AUDIENCES.items():
            for command, _goal, _example in audience["flow"]:
                self.assertIn(
                    command,
                    real,
                    "%r audience references unknown command %r"
                    % (audience_id, command),
                )

    def test_examples_and_related_overrides_reference_real_commands(self):
        real = set(cli_taxonomy.all_commands())
        self.assertEqual([], sorted(set(cli_taxonomy._EXAMPLES) - real))
        self.assertEqual([], sorted(set(cli_taxonomy._RELATED_OVERRIDES) - real))

    def test_related_commands_never_includes_the_command_itself(self):
        for name in cli_taxonomy.all_commands():
            self.assertNotIn(name, cli_taxonomy.related_commands(name))


class PayloadShapeTests(unittest.TestCase):
    def test_catalog_payload_is_json_serializable_and_covers_every_command(self):
        payload = cli_taxonomy.catalog_payload()
        json.dumps(payload)  # must not raise
        self.assertEqual("lifetxt-help-catalog-v1", payload["schema"])
        names = {row["command"] for row in payload["commands"]}
        self.assertEqual(set(cli_taxonomy.all_commands()), names)

    def test_command_record_detailed_includes_arguments_options_examples(self):
        record = cli_taxonomy.command_record("quick", detailed=True)
        json.dumps(record)
        self.assertEqual("quick", record["command"])
        self.assertIn("arguments", record)
        self.assertIn("options", record)
        self.assertIn("examples", record)
        self.assertIn("today", record["related_commands"])

    def test_command_record_lean_omits_detailed_fields(self):
        record = cli_taxonomy.command_record("quick", detailed=False)
        self.assertNotIn("arguments", record)
        self.assertNotIn("options", record)
        self.assertNotIn("examples", record)

    def test_audience_payload_is_json_serializable(self):
        payload = cli_taxonomy.audience_payload("beginner")
        json.dumps(payload)
        self.assertEqual("lifetxt-help-audience-v1", payload["schema"])
        self.assertEqual(5, len(payload["flow"]))
        self.assertEqual(1, payload["flow"][0]["step"])


class CliHelpCommandTests(unittest.TestCase):
    """Exercises `lifetxt help` through the real installed entry point."""

    def test_bare_help_lists_audiences_and_categories(self):
        stdout, stderr, code = run_cli("help")
        self.assertEqual(0, code, stderr)
        self.assertIn("Start here", stdout)
        self.assertIn("lifetxt help beginner", stdout)
        self.assertIn("Getting Started / Daily", stdout)

    def test_help_json_produces_the_full_catalog(self):
        stdout, stderr, code = run_cli("help", "--json")
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertEqual("lifetxt-help-catalog-v1", data["schema"])
        self.assertTrue(any(row["command"] == "today" for row in data["commands"]))

    def test_help_audience_topic(self):
        stdout, stderr, code = run_cli("help", "daily")
        self.assertEqual(0, code, stderr)
        self.assertIn("Daily user", stdout)

    def test_help_command_topic_resolves_alias(self):
        stdout, stderr, code = run_cli("help", "add")
        self.assertEqual(0, code, stderr)
        self.assertIn("lifetxt help quick", stdout)
        self.assertIn("Aliases: q, add", stdout)

    def test_help_command_topic_json(self):
        stdout, stderr, code = run_cli("help", "today", "--json")
        self.assertEqual(0, code, stderr)
        data = json.loads(stdout)
        self.assertEqual("today", data["command"])
        self.assertTrue(data["read_only"])
        self.assertIn("examples", data)

    def test_help_unknown_topic_fails_loudly(self):
        stdout, stderr, code = run_cli("help", "not-a-real-thing")
        self.assertEqual(1, code)
        self.assertIn("Unknown help topic", stderr)

    def test_top_level_help_includes_start_here_and_categories(self):
        stdout, stderr, code = run_cli("--help")
        self.assertEqual(0, code, stderr)
        self.assertIn("Start here", stdout)
        self.assertIn("lifetxt help beginner", stdout)
        self.assertIn("Getting Started / Daily", stdout)
        # The full flat per-command reference must still be present
        # (this block is additive, never a replacement).
        self.assertIn("Additional workflow commands", stdout)

    def test_module_invocation_and_installed_command_agree(self):
        """`python -m lifetxt help` and the installed console script must
        produce identical output, per the issue's explicit compatibility
        requirement."""
        import shutil
        import subprocess
        import sys

        module_stdout, _stderr, module_code = run_cli("help")
        self.assertEqual(0, module_code)

        installed = shutil.which("lifetxt")
        if installed is None:
            self.skipTest("no installed `lifetxt` console script on PATH")
        result = subprocess.run([installed, "help"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(module_stdout, result.stdout)


class CliCategoryDocumentationDriftTests(unittest.TestCase):
    """Covers #629: docs/en/cli.md's category table must track
    cli_taxonomy.CATEGORIES. Nothing enforced this before -- the two were
    kept in sync by hand, which drifts silently on the next command
    addition, removal, or re-categorization.
    """

    def _repo_docs_path(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(repo_root, "docs", "en", "cli.md")

    def test_docs_category_table_matches_the_taxonomy_registry(self):
        documented = _docs_categories(self._repo_docs_path())
        registered = {
            category["title"]: list(category["commands"])
            for category in cli_taxonomy.CATEGORIES.values()
        }

        missing_from_docs = sorted(set(registered) - set(documented))
        stale_in_docs = sorted(set(documented) - set(registered))
        self.assertEqual(
            [], missing_from_docs, "categories missing from docs/en/cli.md"
        )
        self.assertEqual(
            [],
            stale_in_docs,
            "docs/en/cli.md documents categories no longer in cli_taxonomy.CATEGORIES",
        )

        mismatches = [
            "%r: docs commands %r != registry commands %r"
            % (title, documented[title], registered[title])
            for title in sorted(set(documented) & set(registered))
            if documented[title] != registered[title]
        ]
        self.assertEqual([], mismatches)


if __name__ == "__main__":
    unittest.main()
