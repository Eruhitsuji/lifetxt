import os
import re
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACEABILITY_PATH = ".ai/project/TRACEABILITY.yml"
CODE_CHANGE_PREFIXES = ("lifetxt/", "tests/")
DEFAULT_BASE_BRANCH = "origin/main"
ISSUE_URL_RE = re.compile(r"^https://github\.com/Eruhitsuji/lifetxt/issues/[0-9]+$")


@dataclass
class TraceabilityGateResult:
    ok: bool
    reason: str
    changed_files: tuple[str, ...] = ()
    added_traceability_lines: tuple[str, ...] = ()


def evaluate_traceability_gate(root, base, head="HEAD", pr_url=None):
    changed_files = _changed_files(root, base, head)
    code_changed = tuple(
        path for path in changed_files if path.startswith(CODE_CHANGE_PREFIXES)
    )
    if not code_changed:
        return TraceabilityGateResult(
            True,
            "No lifetxt/** or tests/** changes require a traceability update.",
            changed_files=changed_files,
        )
    added_lines = _added_traceability_lines(root, base, head)
    if TRACEABILITY_PATH not in changed_files:
        return TraceabilityGateResult(
            False,
            "Code changed without updating .ai/project/TRACEABILITY.yml.",
            changed_files=changed_files,
            added_traceability_lines=added_lines,
        )
    if _has_meaningful_chain_update(added_lines, pr_url=pr_url):
        return TraceabilityGateResult(
            True,
            "Code change has a meaningful traceability chain update.",
            changed_files=changed_files,
            added_traceability_lines=added_lines,
        )
    if _has_not_applicable_exception(added_lines, pr_url=pr_url):
        return TraceabilityGateResult(
            True,
            "Code change has a recorded traceability not-applicable exception.",
            changed_files=changed_files,
            added_traceability_lines=added_lines,
        )
    return TraceabilityGateResult(
        False,
        "Traceability changed, but no meaningful chain update or not-applicable "
        "exception was added.",
        changed_files=changed_files,
        added_traceability_lines=added_lines,
    )


def infer_local_base(root):
    try:
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    except RuntimeError:
        return None
    if branch in ("HEAD", "main", "master"):
        return None
    try:
        _git(root, "rev-parse", "--verify", DEFAULT_BASE_BRANCH)
    except RuntimeError:
        return None
    return DEFAULT_BASE_BRANCH


def _changed_files(root, base, head):
    output = _git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=ACDMRT",
        "%s...%s" % (base, head),
    )
    return tuple(
        line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()
    )


def _added_traceability_lines(root, base, head):
    output = _git(
        root,
        "diff",
        "--unified=0",
        "--no-ext-diff",
        "%s...%s" % (base, head),
        "--",
        TRACEABILITY_PATH,
    )
    lines = []
    for raw in output.splitlines():
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        line = raw[1:].rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line)
    return tuple(lines)


def _has_meaningful_chain_update(lines, pr_url=None):
    return (
        _has_non_empty_value(lines, "requirement_id")
        and _has_non_empty_value(lines, "capability_id")
        and _has_issue_url(lines)
        and _has_non_empty_value_or_sequence_item(lines, "tests_or_evidence")
        and _has_non_empty_value(lines, "status")
        and _pr_requirement_is_met(lines, pr_url)
    )


def _has_not_applicable_exception(lines, pr_url=None):
    return (
        _has_exact_value(lines, "exception_type", "traceability_not_applicable")
        and _has_issue_url(lines)
        and _has_non_empty_value(lines, "scope")
        and _has_non_empty_value(lines, "reason")
        and _has_non_empty_value(lines, "approved_by")
        and _has_exact_value(lines, "status", "accepted")
        and _pr_requirement_is_met(lines, pr_url)
    )


def _pr_requirement_is_met(lines, pr_url):
    if not pr_url:
        return True
    return _has_exact_value(lines, "pull_request", pr_url)


def _has_issue_url(lines):
    return any(ISSUE_URL_RE.match(value) for value in _values(lines, "task_issue"))


def _has_non_empty_value(lines, key):
    return any(value not in ("", "null", "None") for value in _values(lines, key))


def _has_non_empty_value_or_sequence_item(lines, key):
    if _has_non_empty_value(lines, key):
        return True
    marker = key + ":"
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if not stripped.startswith(marker):
            continue
        key_indent = len(line) - len(line.lstrip(" "))
        for nested in lines[index + 1 :]:
            nested_indent = len(nested) - len(nested.lstrip(" "))
            nested_stripped = nested.strip()
            if nested_indent <= key_indent:
                break
            if nested_indent > key_indent and nested_stripped.startswith("- "):
                return True
    return False


def _has_exact_value(lines, key, expected):
    return any(value == expected for value in _values(lines, key))


def _values(lines, key):
    prefix = key + ":"
    values = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if not stripped.startswith(prefix):
            continue
        values.append(stripped[len(prefix) :].strip().strip("'\""))
    return values


def _git(root, *args):
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


class TraceabilityGatePolicyTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is required to exercise the traceability gate")
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "test@example.invalid")
        _git(self.root, "config", "user.name", "Traceability Gate Test")
        self.write(
            TRACEABILITY_PATH, "schema_version: 1\ntraceability:\n  chains: []\n"
        )
        self.write("lifetxt/__init__.py", "\n")
        self.write("tests/__init__.py", "\n")
        self.commit("baseline")
        self.base = _git(self.root, "rev-parse", "HEAD").strip()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        absolute = os.path.join(self.root, *path.split("/"))
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def append(self, path, text):
        absolute = os.path.join(self.root, *path.split("/"))
        with open(absolute, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def delete(self, path):
        os.remove(os.path.join(self.root, *path.split("/")))

    def commit(self, message):
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-m", message)

    def evaluate(self, pr_url="https://github.com/Eruhitsuji/lifetxt/pull/123"):
        return evaluate_traceability_gate(self.root, self.base, pr_url=pr_url)

    def test_code_change_without_traceability_update_fails(self):
        self.write("lifetxt/module.py", "VALUE = 1\n")
        self.commit("code change")

        result = self.evaluate()

        self.assertFalse(result.ok)
        self.assertIn("Code changed without updating", result.reason)

    def test_deleted_code_without_traceability_update_fails(self):
        self.delete("lifetxt/__init__.py")
        self.commit("delete code")

        result = self.evaluate()

        self.assertFalse(result.ok)
        self.assertIn("Code changed without updating", result.reason)

    def test_non_code_change_without_traceability_update_passes(self):
        self.write("docs/note.md", "notes\n")
        self.commit("docs only")

        result = self.evaluate()

        self.assertTrue(result.ok, result)

    def test_code_change_with_meaningful_traceability_chain_passes(self):
        self.write("tests/test_new_behavior.py", "def test_placeholder():\n    pass\n")
        self.append(
            TRACEABILITY_PATH,
            "    - requirement_id: req-ai-standard-guided-activation\n"
            "      capability_id: cap-ai-standard-guided-activation\n"
            "      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/88\n"
            "      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/123\n"
            "      tests_or_evidence:\n"
            "        - traceability gate exercised\n"
            "      status: implemented\n",
        )
        self.commit("code with trace")

        result = self.evaluate()

        self.assertTrue(result.ok, result)

    def test_meaningful_traceability_chain_with_wrong_pr_url_fails(self):
        self.write("tests/test_new_behavior.py", "def test_placeholder():\n    pass\n")
        self.append(
            TRACEABILITY_PATH,
            "    - requirement_id: req-ai-standard-guided-activation\n"
            "      capability_id: cap-ai-standard-guided-activation\n"
            "      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/88\n"
            "      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/999\n"
            "      tests_or_evidence:\n"
            "        - traceability gate exercised\n"
            "      status: implemented\n",
        )
        self.commit("code with wrong trace pr")

        result = self.evaluate()

        self.assertFalse(result.ok)
        self.assertIn("no meaningful chain update", result.reason)

    def test_empty_tests_or_evidence_sequence_does_not_satisfy_gate(self):
        self.write("tests/test_new_behavior.py", "def test_placeholder():\n    pass\n")
        self.append(
            TRACEABILITY_PATH,
            "    - requirement_id: req-ai-standard-guided-activation\n"
            "      capability_id: cap-ai-standard-guided-activation\n"
            "      task_issue: https://github.com/Eruhitsuji/lifetxt/issues/88\n"
            "      pull_request: https://github.com/Eruhitsuji/lifetxt/pull/123\n"
            "      tests_or_evidence:\n"
            "      changed_files_or_scope:\n"
            "        - tests/test_new_behavior.py\n"
            "      status: implemented\n",
        )
        self.commit("code with empty evidence")

        result = self.evaluate()

        self.assertFalse(result.ok)
        self.assertIn("no meaningful chain update", result.reason)

    def test_cosmetic_traceability_edit_does_not_satisfy_code_change(self):
        self.write("lifetxt/module.py", "VALUE = 2\n")
        self.append(TRACEABILITY_PATH, "# comment only\n")
        self.commit("cosmetic trace")

        result = self.evaluate()

        self.assertFalse(result.ok)
        self.assertIn("no meaningful chain update", result.reason)

    def test_code_change_with_recorded_not_applicable_exception_passes(self):
        self.write(
            "tests/test_not_applicable.py", "def test_placeholder():\n    pass\n"
        )
        self.append(
            TRACEABILITY_PATH,
            "exceptions:\n"
            "  - exception_type: traceability_not_applicable\n"
            "    task_issue: https://github.com/Eruhitsuji/lifetxt/issues/88\n"
            "    pull_request: https://github.com/Eruhitsuji/lifetxt/pull/123\n"
            "    scope: test-only fixture change\n"
            "    reason: no product or process traceability chain changed\n"
            "    approved_by: Eruhitsuji\n"
            "    status: accepted\n",
        )
        self.commit("code with exception")

        result = self.evaluate()

        self.assertTrue(result.ok, result)

    def test_not_applicable_exception_without_reason_fails(self):
        self.write(
            "tests/test_not_applicable.py", "def test_placeholder():\n    pass\n"
        )
        self.append(
            TRACEABILITY_PATH,
            "exceptions:\n"
            "  - exception_type: traceability_not_applicable\n"
            "    task_issue: https://github.com/Eruhitsuji/lifetxt/issues/88\n"
            "    pull_request: https://github.com/Eruhitsuji/lifetxt/pull/123\n"
            "    scope: test-only fixture change\n"
            "    approved_by: Eruhitsuji\n"
            "    status: accepted\n",
        )
        self.commit("code with incomplete exception")

        result = self.evaluate()

        self.assertFalse(result.ok)


class RepositoryTraceabilityGateTests(unittest.TestCase):
    def test_current_change_set_satisfies_traceability_gate_when_base_is_known(self):
        base = os.environ.get("LIFETXT_TRACEABILITY_GATE_BASE") or infer_local_base(
            ROOT
        )
        if not base:
            return
        pr_url = os.environ.get("LIFETXT_TRACEABILITY_GATE_PR_URL")
        result = evaluate_traceability_gate(ROOT, base, pr_url=pr_url)
        self.assertTrue(
            result.ok,
            "%s\nChanged files: %s\nAdded traceability lines: %s"
            % (result.reason, result.changed_files, result.added_traceability_lines),
        )


if __name__ == "__main__":
    unittest.main()
