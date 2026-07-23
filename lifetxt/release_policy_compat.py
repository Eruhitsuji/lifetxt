"""Compatibility and migration policy for executable release checks.

Python 3.10 does not provide tomllib, and the existing Web translation debt must
be visible without allowing newly introduced gaps.  These adapters preserve a
dependency-free normal install while making the full release manifest strict
about new regressions.
"""

from __future__ import unicode_literals

import json
import os
import re
from collections import OrderedDict

TRANSLATION_BASELINE_PATH = os.path.join(
    "config", "release", "web-ja-translation-baseline-v1.json"
)


def install_release_policy_compatibility():
    from . import release_policy

    if getattr(release_policy, "_lifetxt_release_compat_installed", False):
        return
    original_packaging = release_policy.packaging_metadata_report
    original_manifest = release_policy.release_manifest

    def packaging_metadata_report(root):
        report = original_packaging(root)
        errors = " ".join(str(value) for value in report.get("errors") or [])
        if report.get("ok") or "tomli" not in errors:
            return report
        return _fallback_packaging_metadata_report(root)

    def release_manifest(root, paths=None, require_validator=True):
        manifest = original_manifest(
            root,
            paths=paths,
            require_validator=require_validator,
        )
        manifest["checks"]["translation_coverage"] = translation_policy_report(root)
        manifest["checks"]["release_policy_definition"] = release_policy_definition_report(
            root,
            manifest["checks"],
        )
        manifest["ok"] = all(
            bool(report.get("ok")) for report in manifest["checks"].values()
        )
        manifest["fingerprint"] = release_policy._manifest_fingerprint(manifest)
        return manifest

    release_policy.packaging_metadata_report = packaging_metadata_report
    release_policy.release_manifest = release_manifest
    release_policy._lifetxt_release_compat_installed = True


def _section(text, name):
    marker = "[%s]" % name
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    match = re.search(r"^\s*\[[^\]]+\]\s*$", text[start:], re.M)
    end = start + match.start() if match else len(text)
    return text[start:end]


def _string_value(block, key):
    match = re.search(
        r'^\s*%s\s*=\s*(["\'])(.*?)\1\s*$' % re.escape(key),
        block,
        re.M,
    )
    return match.group(2) if match else None


def _fallback_packaging_metadata_report(root):
    path = os.path.join(root, "pyproject.toml")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        return OrderedDict((("ok", False), ("errors", [str(exc)])))

    project = _section(text, "project")
    scripts = _section(text, "project.scripts")
    extras = _section(text, "project.optional-dependencies")
    from . import __version__

    values = {
        "name": _string_value(project, "name"),
        "version": _string_value(project, "version"),
        "readme": _string_value(project, "readme"),
        "requires-python": _string_value(project, "requires-python"),
        "console_script": _string_value(scripts, "lifetxt"),
    }
    errors = []
    for key, expected in (
        ("name", "lifetxt"),
        ("version", __version__),
        ("readme", "readme.md"),
    ):
        if values[key] != expected:
            errors.append("project.%s must be %r." % (key, expected))
    if values["console_script"] != "lifetxt.entrypoint:main":
        errors.append("project.scripts.lifetxt must point to lifetxt.entrypoint:main.")
    available_extras = sorted(
        name
        for name in ("web", "tui")
        if re.search(r"^\s*%s\s*=\s*\[" % re.escape(name), extras, re.M)
    )
    for name in ("web", "tui"):
        if name not in available_extras:
            errors.append("project.optional-dependencies.%s is missing or empty." % name)
    if not values["requires-python"]:
        errors.append("project.requires-python is required.")
    if not re.search(r"^\s*license\s*=", project, re.M):
        errors.append("project.license is required.")
    return OrderedDict(
        (
            ("ok", not errors),
            ("errors", errors),
            ("name", values["name"]),
            ("version", values["version"]),
            ("console_script", values["console_script"]),
            ("extras", available_extras),
            ("parser", "dependency-free fallback"),
        )
    )


def translation_policy_report(root):
    from . import release_policy

    strict = release_policy.translation_coverage_report()
    path = os.path.join(root, TRANSLATION_BASELINE_PATH)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            baseline = json.load(handle, object_pairs_hook=OrderedDict)
    except Exception as exc:
        result = OrderedDict(strict)
        result["ok"] = False
        result["baseline_error"] = str(exc)
        result["new_missing"] = list(strict.get("missing") or [])
        return result

    current = set(str(value) for value in strict.get("missing") or [])
    known = set(str(value) for value in baseline.get("known_missing") or [])
    new_missing = sorted(current - known)
    known_missing = sorted(current & known)
    resolved = sorted(known - current)
    result = OrderedDict(strict)
    result["ok"] = not new_missing and "error" not in strict
    result["baseline_version"] = baseline.get("baseline_version")
    result["all_missing"] = sorted(current)
    result["known_missing"] = known_missing
    result["new_missing"] = new_missing
    result["resolved_baseline_entries"] = resolved
    result["missing"] = new_missing
    return result


def release_policy_definition_report(root, checks):
    from . import release_policy

    path = os.path.join(root, release_policy.RELEASE_POLICY_PATH)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            policy = json.load(handle, object_pairs_hook=OrderedDict)
    except Exception as exc:
        return OrderedDict((("ok", False), ("errors", [str(exc)])))

    errors = []
    if str(policy.get("policy_version")) != release_policy.POLICY_VERSION:
        errors.append(
            "Release policy_version must be %s." % release_policy.POLICY_VERSION
        )
    required = [str(value) for value in policy.get("required_checks") or []]
    available = set(checks)
    missing = sorted(set(required) - available)
    if missing:
        errors.append("Required release checks are unavailable: %s." % ", ".join(missing))
    duplicate = len(required) != len(set(required))
    if duplicate:
        errors.append("required_checks contains duplicate names.")
    requirements = policy.get("release_requires") or {}
    disabled = sorted(key for key, value in requirements.items() if value is not True)
    if disabled:
        errors.append(
            "Release requirements must be explicitly true: %s." % ", ".join(disabled)
        )
    return OrderedDict(
        (
            ("ok", not errors),
            ("errors", errors),
            ("policy_version", policy.get("policy_version")),
            ("required_checks", required),
            ("available_checks", sorted(available)),
            ("release_requires", requirements),
        )
    )
