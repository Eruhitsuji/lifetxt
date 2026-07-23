"""Executable release policy for lifetxt.

The normal package remains dependency-free.  This module can run a useful
subset without optional packages, while the release CI profile installs the
standards-compliant JSON Schema validator and packaging tools required for the
full gate.
"""

from __future__ import unicode_literals

import hashlib
import json
import os
import re
from collections import OrderedDict
from html.parser import HTMLParser

from . import __version__
from .mutation import MutationConflict
from .safety_foundation import (
    CANON_VERSION,
    CAPABILITY_VERSION,
    FORMAT_VERSION,
    SCHEMA_VERSION,
    _cas_probe,
    _timezone_probe,
    audit_python_writes,
    capability_document,
    canonicalize_text,
    schema_bundle,
    stable_diagnostics,
)

POLICY_VERSION = "1"
RELEASE_POLICY_PATH = os.path.join("config", "release", "policy-v1.json")
WRITE_BASELINE_PATH = os.path.join("config", "release", "write-route-baseline-v1.json")
GOLDEN_POLICY_PATH = os.path.join("tests", "golden", "policy-v1.json")
GOLDEN_CORPUS_PATH = os.path.join("tests", "golden", "roundtrip_cases.json")


class _ChromeParser(HTMLParser):
    """Collect user-visible static chrome while excluding authored content."""

    VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"))
    ATTRIBUTES = frozenset(("title", "placeholder", "aria-label", "data-help"))
    SKIP_TAGS = frozenset(("script", "style", "textarea", "code", "pre"))

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.stack = []
        self.skip_depth = 0
        self.record_depth = 0
        self.strings = set()
        self.excluded_record_nodes = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(str(attrs.get("class") or "").split())
        skip = tag in self.SKIP_TAGS
        record = "data-no-i18n" in attrs or bool(classes.intersection(_record_classes()))
        if skip:
            self.skip_depth += 1
        if record:
            self.record_depth += 1
            self.excluded_record_nodes += 1
        if not self.skip_depth and not self.record_depth:
            for name in self.ATTRIBUTES:
                if attrs.get(name):
                    self._add(attrs[name])
        if tag not in self.VOID:
            self.stack.append((tag, skip, record))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        popped = []
        while self.stack:
            entry = self.stack.pop()
            popped.append(entry)
            if entry[0] == tag:
                break
        for _name, skip, record in popped:
            if skip:
                self.skip_depth = max(0, self.skip_depth - 1)
            if record:
                self.record_depth = max(0, self.record_depth - 1)

    def handle_data(self, data):
        if not self.skip_depth and not self.record_depth:
            self._add(data)

    def _add(self, value):
        value = _normalize_space(value)
        if _is_chrome_candidate(value):
            self.strings.add(value)


def _record_classes():
    return frozenset(
        (
            "item", "item-title", "title", "meta", "source", "tl-entry",
            "tl-title", "cal-entry", "cal-entry-title", "focus-row",
            "focus-row-title", "focus-row-main", "focus-row-meta", "team-card",
            "msg-row", "diagnostic", "dash-item", "kpi-value", "dash-row-title",
            "person-status-title", "person-msg-title", "person-meta", "tl-card-title",
            "tl-card-meta", "message-thread-meta",
        )
    )


def _normalize_space(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_chrome_candidate(value):
    if not value or value in ("life.txt", "✓", "⌘", "◑", "⏸", "▤", "⛶", "🌙"):
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    if value.startswith(("http://", "https://", "/api/")):
        return False
    if "${" in value or "{{" in value:
        return False
    if re.fullmatch(r"[A-Za-z0-9_+./<>?\[\](),:;=-]{1,18}", value):
        return False
    return True


def _extract_braced(text, marker):
    start = text.find(marker)
    if start < 0:
        raise ValueError("Could not find %s." % marker)
    brace = text.find("{", start)
    if brace < 0:
        raise ValueError("Could not find object body after %s." % marker)
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    index = brace
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
                continue
            index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"', "`"):
            quote = char
        elif char == "/" and nxt == "/":
            line_comment = True
            index += 2
            continue
        elif char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace:index + 1]
        index += 1
    raise ValueError("Unterminated object after %s." % marker)


def _js_quoted_values(text):
    values = []
    pattern = re.compile(r'(["\'])(.*?)(?<!\\)\1', re.S)
    for match in pattern.finditer(text):
        raw = match.group(2)
        try:
            value = bytes(raw, "utf-8").decode("unicode_escape") if "\\" in raw else raw
        except UnicodeDecodeError:
            value = raw
        values.append(value)
    return values


def _dictionary_keys(html):
    whole = _extract_braced(html, "const UI_STRINGS")
    ja = _extract_braced(whole, "ja:")
    return set(
        match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        for match in re.finditer(r'^\s*"((?:\\.|[^"\\])*)"\s*:', ja, re.M)
    )


def _dynamic_translation_literals(html):
    result = set()
    for quote, value in re.findall(r'\bt\(\s*(["\'])((?:\\.|(?!\1).)*)\1\s*[),]', html):
        del quote
        value = value.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
        if _is_chrome_candidate(value):
            result.add(_normalize_space(value))
    return result


def _translation_candidates(value):
    values = [value]
    core = re.sub(r"^[^A-Za-z0-9]+", "", value).strip()
    if core and core not in values:
        values.append(core)
    stripped = re.sub(r"\s*[\(（][^\)）]*[\)）]\s*$", "", core).strip()
    if stripped and stripped not in values:
        values.append(stripped)
    return values


def translation_coverage_report(html=None):
    if html is None:
        from .webapp import HTML_PAGE
        html = HTML_PAGE
    try:
        keys = _dictionary_keys(html)
        parser = _ChromeParser()
        parser.feed(html)
        dynamic = _dynamic_translation_literals(html)
        candidates = set(parser.strings) | dynamic
        missing = []
        for value in sorted(candidates):
            if not any(candidate in keys for candidate in _translation_candidates(value)):
                missing.append(value)
        return OrderedDict(
            (
                ("ok", not missing),
                ("dictionary_entries", len(keys)),
                ("chrome_strings", len(parser.strings)),
                ("dynamic_strings", len(dynamic)),
                ("excluded_record_nodes", parser.excluded_record_nodes),
                ("missing", missing),
            )
        )
    except Exception as exc:
        return OrderedDict((("ok", False), ("error", str(exc)), ("missing", [])))


def packaging_metadata_report(root):
    path = os.path.join(root, "pyproject.toml")
    if not os.path.exists(path):
        return OrderedDict((("ok", False), ("errors", ["pyproject.toml is missing."])))
    try:
        try:
            import tomllib
        except ImportError:  # pragma: no cover - Python 3.10 release jobs use tomli
            import tomli as tomllib
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except Exception as exc:
        return OrderedDict((("ok", False), ("errors", [str(exc)])))
    project = data.get("project") or {}
    errors = []
    expected = {
        "name": "lifetxt",
        "version": __version__,
        "readme": "readme.md",
    }
    for key, value in expected.items():
        if project.get(key) != value:
            errors.append("project.%s must be %r." % (key, value))
    scripts = project.get("scripts") or {}
    if scripts.get("lifetxt") != "lifetxt.entrypoint:main":
        errors.append("project.scripts.lifetxt must point to lifetxt.entrypoint:main.")
    extras = project.get("optional-dependencies") or {}
    for name in ("web", "tui"):
        if not extras.get(name):
            errors.append("project.optional-dependencies.%s is missing or empty." % name)
    if not project.get("requires-python"):
        errors.append("project.requires-python is required.")
    if not project.get("license"):
        errors.append("project.license is required.")
    return OrderedDict(
        (
            ("ok", not errors),
            ("errors", errors),
            ("name", project.get("name")),
            ("version", project.get("version")),
            ("console_script", scripts.get("lifetxt")),
            ("extras", sorted(extras)),
        )
    )


def golden_policy_report(root):
    errors = []
    policy_path = os.path.join(root, GOLDEN_POLICY_PATH)
    corpus_path = os.path.join(root, GOLDEN_CORPUS_PATH)
    try:
        policy = _load_json(policy_path)
        corpus = _load_json(corpus_path)
    except Exception as exc:
        return OrderedDict((("ok", False), ("errors", [str(exc)])))
    if str(policy.get("policy_version")) != POLICY_VERSION:
        errors.append("Golden policy_version must be %s." % POLICY_VERSION)
    if int(policy.get("corpus_version") or 0) != int(corpus.get("version") or 0):
        errors.append("Golden policy corpus_version does not match the corpus.")
    cases = corpus.get("cases") or []
    minimum = int(policy.get("minimum_cases") or 1)
    if len(cases) < minimum:
        errors.append("Golden corpus has %d cases; policy requires %d." % (len(cases), minimum))
    names = [str(case.get("name") or "") for case in cases]
    if len(names) != len(set(names)) or not all(names):
        errors.append("Golden case names must be non-empty and unique.")
    required = set(policy.get("required_fields") or ("name", "input", "canonical"))
    for case in cases:
        missing = sorted(required - set(case))
        if missing:
            errors.append("Golden case %r is missing %s." % (case.get("name"), ", ".join(missing)))
        canonical = str(case.get("canonical") or "")
        if canonicalize_text(canonical) != canonical:
            errors.append("Golden case %r canonical output is not canonically normalized." % case.get("name"))
    required_names = set(policy.get("required_cases") or [])
    absent = sorted(required_names - set(names))
    if absent:
        errors.append("Required golden cases are absent: %s." % ", ".join(absent))
    return OrderedDict(
        (
            ("ok", not errors),
            ("errors", errors),
            ("policy_version", policy.get("policy_version")),
            ("corpus_version", corpus.get("version")),
            ("case_count", len(cases)),
            ("case_names", names),
        )
    )


def schema_validation_report(root, require_validator=True):
    errors = []
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return OrderedDict(
            (
                ("ok", not require_validator),
                ("validator_available", False),
                ("errors", ["Install jsonschema for the full release gate."] if require_validator else []),
            )
        )
    generated = schema_bundle()
    published = OrderedDict()
    schema_dir = os.path.join(root, "dist", "schemas")
    for name, schema in generated.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append("Generated %s is invalid: %s" % (name, exc))
        path = os.path.join(schema_dir, name)
        try:
            published[name] = _load_json(path)
        except Exception as exc:
            errors.append("Published %s cannot be read: %s" % (name, exc))
            continue
        if published[name] != schema:
            errors.append("Published %s differs from schema_bundle()." % name)
        try:
            Draft202012Validator.check_schema(published[name])
        except Exception as exc:
            errors.append("Published %s is invalid: %s" % (name, exc))
    samples = _schema_samples()
    for name, sample in samples.items():
        schema = generated.get(name)
        if schema is None:
            errors.append("No schema exists for sample %s." % name)
            continue
        for error in Draft202012Validator(schema).iter_errors(sample):
            errors.append("Sample %s failed: %s" % (name, error.message))
    return OrderedDict(
        (
            ("ok", not errors),
            ("validator_available", True),
            ("draft", "2020-12"),
            ("schema_count", len(generated)),
            ("sample_count", len(samples)),
            ("errors", errors),
        )
    )


def _schema_samples():
    conflict = MutationConflict("life.txt", "old", "new", operation="test")
    return OrderedDict(
        (
            (
                "item-v1.schema.json",
                {"status": "[ ]", "type": "T", "title": "Sample", "details": {"id": ["T-1"]}},
            ),
            (
                "diagnostic-v1.schema.json",
                {
                    "severity": "warning", "code": "F101", "message": "Sample",
                    "source": "life.txt", "line": 1, "column": 1,
                    "span": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 1}},
                    "hint": "Fix it.",
                },
            ),
            ("capability-v1.schema.json", capability_document()),
            (
                "conflict-v1.schema.json",
                {
                    "error": "CONFLICT", "expected_revision": conflict.expected_hash,
                    "current_revision": conflict.actual_hash, "current_item": None,
                    "attempted_change": {"operation": conflict.operation},
                },
            ),
        )
    )


def write_route_baseline_report(root):
    baseline_path = os.path.join(root, WRITE_BASELINE_PATH)
    try:
        baseline = _load_json(baseline_path)
    except Exception as exc:
        return OrderedDict((("ok", False), ("errors", [str(exc)]), ("new_findings", [])))
    allowed = set()
    for row in baseline.get("allowed") or []:
        allowed.add((str(row.get("path") or "").replace("\\", "/"), str(row.get("call") or "")))
    current = []
    for finding in audit_python_writes(root):
        relative = os.path.relpath(finding["path"], root).replace("\\", "/")
        current.append({"path": relative, "line": finding["line"], "call": finding["call"]})
    new_findings = [row for row in current if (row["path"], row["call"]) not in allowed]
    current_pairs = set((row["path"], row["call"]) for row in current)
    stale = [
        {"path": path, "call": call}
        for path, call in sorted(allowed - current_pairs)
    ]
    return OrderedDict(
        (
            ("ok", not new_findings),
            ("baseline_version", baseline.get("baseline_version")),
            ("finding_count", len(current)),
            ("new_findings", new_findings),
            ("stale_allowances", stale),
        )
    )


def release_manifest(root, paths=None, require_validator=True):
    reports = OrderedDict()
    reports["mutation_cas"] = {"ok": bool(_cas_probe())}
    reports["timezone_roundtrip"] = {"ok": bool(_timezone_probe())}
    reports["packaging_metadata"] = packaging_metadata_report(root)
    reports["golden_policy"] = golden_policy_report(root)
    reports["schema_validation"] = schema_validation_report(root, require_validator=require_validator)
    reports["translation_coverage"] = translation_coverage_report()
    reports["write_route_baseline"] = write_route_baseline_report(root)
    for path in paths or []:
        try:
            reports["format:%s" % path] = stable_diagnostics(path)
        except OSError as exc:
            reports["format:%s" % path] = {"ok": False, "error": str(exc)}
    manifest = OrderedDict(
        (
            ("release_policy_version", POLICY_VERSION),
            ("package", "lifetxt"),
            ("package_version", __version__),
            ("versions", {"format": FORMAT_VERSION, "canon": CANON_VERSION, "schema": SCHEMA_VERSION, "capability": CAPABILITY_VERSION}),
            ("checks", reports),
        )
    )
    manifest["ok"] = all(bool(report.get("ok")) for report in reports.values())
    manifest["fingerprint"] = _manifest_fingerprint(manifest)
    return manifest


def release_gate(root, paths=None, require_validator=True):
    """Return the CLI-compatible release gate shape with detailed policy checks."""
    manifest = release_manifest(root, paths=paths, require_validator=require_validator)
    checks = []
    for name, detail in manifest["checks"].items():
        checks.append(OrderedDict((("name", name), ("ok", bool(detail.get("ok"))), ("detail", detail))))
    return OrderedDict(
        (
            ("ok", manifest["ok"]),
            ("checks", checks),
            ("versions", manifest["versions"]),
            ("release_policy_version", manifest["release_policy_version"]),
            ("fingerprint", manifest["fingerprint"]),
        )
    )


def _manifest_fingerprint(manifest):
    stable = OrderedDict((key, value) for key, value in manifest.items() if key != "fingerprint")
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)
