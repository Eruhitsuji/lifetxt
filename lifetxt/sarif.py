"""SARIF 2.1.0 export adapter for `lifetxt check` (#644).

This is a pure, read-only serializer over the already-filtered, stable
`Diagnostic` list `check` already computes -- it never re-runs or
re-implements any parser/validator rule, never invents a diagnostic code
or category (`category` is reused from `diagnostic_contract.py`'s existing
`diagnostic_category()`, never re-mapped by hand), and never guesses an end
position a diagnostic does not already carry. It has no network, upload,
or credential handling of any kind: it only ever returns a JSON-serializable
document for the caller to write wherever it likes (stdout, a file for
`gh code-scanning`-style upload, an editor extension, ...).

Mapping (see the SARIF 2.1.0 spec, section 3):

    Diagnostic.code                 -> result.ruleId (and one deduplicated
                                        tool.driver.rules[] entry per code)
    Diagnostic.severity             -> result.level ("error"/"warning";
                                        see SEVERITY_TO_LEVEL)
    Diagnostic.message              -> result.message.text
    Diagnostic.source               -> result.locations[0].physicalLocation
                                        .artifactLocation.uri (see _to_uri)
    Diagnostic.line/column           -> region.startLine/startColumn
                                        (SARIF columns are 1-based UTF-16
                                        code-unit offsets, matching
                                        lifetxt's own 1-based column
                                        convention exactly -- no offset
                                        conversion is applied)
    Diagnostic.end_line/end_column   -> region.endLine/endColumn, added
                                        only when both are already known;
                                        a diagnostic with no known end
                                        position gets a start-only region
    Diagnostic.hint                  -> result.properties.hint (when
                                        non-empty)
    diagnostic_category(diagnostic)  -> rule.properties.category
"""

from __future__ import unicode_literals

import json
import re
from collections import OrderedDict
from urllib.parse import quote

from .diagnostic_contract import diagnostic_category

SARIF_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/"
    "sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"
TOOL_NAME = "lifetxt"
TOOL_INFORMATION_URI = "https://github.com/Eruhitsuji/lifetxt"

#: Deterministic, total mapping from lifetxt's two real severities to a
#: SARIF result level. Anything else (there is no third severity in this
#: codebase today) conservatively falls back to "warning" rather than
#: raising, so a future severity value degrades safely instead of crashing
#: SARIF generation.
SEVERITY_TO_LEVEL = {
    "error": "error",
    "warning": "warning",
}

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")
#: A UNC path after backslash normalization: "//host/share/rest...". The
#: host is its own URI authority component (RFC 8089's Windows UNC-path
#: appendix); "rest" is an ordinary path.
_UNC_RE = re.compile(r"^//([^/]+)(/.*)?$")


def _to_uri(path):
    """Convert a `Diagnostic.source` path to a SARIF `artifactLocation.uri`.

    Handles both platform path styles: an absolute Windows path
    (`C:\\Users\\...` or already-forward-slashed `C:/Users/...`) becomes
    `file:///C:/Users/...`; a UNC path (`\\\\server\\share\\...`) becomes
    `file://server/share/...`, with the server name as the URI's own
    authority component rather than folded into the path (which would
    otherwise produce a non-standard four-slash `file:////server/...`);
    an absolute POSIX path becomes `file:///...`; a relative path (the
    common case -- most `check` invocations pass a relative life.txt
    path) is used as-is, with backslashes normalized to forward slashes,
    which SARIF's own relative-URI-reference form permits directly with
    no scheme.

    Every path segment is percent-encoded (`urllib.parse.quote`, leaving
    only `/` -- and `:` for a Windows drive letter -- unescaped) so a
    path containing a space, `#`, or non-ASCII character (all valid on
    both Windows and POSIX filesystems) produces a well-formed URI a
    SARIF consumer can actually resolve, rather than one where `#`
    would be read as introducing a URI fragment and a literal space
    would make the URI invalid outright -- a CodeX review finding
    against the original unescaped version.
    """
    if not path or path == "-":
        return None
    normalized = str(path).replace("\\", "/")
    if _WINDOWS_DRIVE_RE.match(normalized):
        return "file:///" + quote(normalized, safe="/:")
    unc_match = _UNC_RE.match(normalized)
    if unc_match:
        host, rest = unc_match.group(1), unc_match.group(2) or ""
        return "file://" + quote(host, safe="") + quote(rest, safe="/")
    if normalized.startswith("/"):
        return "file://" + quote(normalized, safe="/")
    return quote(normalized, safe="/")


def _region(diagnostic):
    if diagnostic.line is None:
        return None
    region = OrderedDict()
    region["startLine"] = diagnostic.line
    if diagnostic.column is not None:
        region["startColumn"] = diagnostic.column
    if diagnostic.end_line is not None and diagnostic.end_column is not None:
        region["endLine"] = diagnostic.end_line
        region["endColumn"] = diagnostic.end_column
    return region


def _location(diagnostic):
    uri = _to_uri(diagnostic.source)
    if uri is None and diagnostic.line is None:
        return None
    physical_location = OrderedDict()
    if uri is not None:
        physical_location["artifactLocation"] = OrderedDict((("uri", uri),))
    region = _region(diagnostic)
    if region:
        physical_location["region"] = region
    if not physical_location:
        return None
    return OrderedDict((("physicalLocation", physical_location),))


def _rule(code, category):
    rule = OrderedDict()
    rule["id"] = code
    rule["name"] = code
    rule["properties"] = OrderedDict((("category", category),))
    try:
        from . import diagnostic_catalog

        record = diagnostic_catalog.explain_record(code)
    except ValueError:
        pass
    else:
        rule["shortDescription"] = OrderedDict((("text", record["summary"]),))
    return rule


def _result(diagnostic):
    code = diagnostic.code or ""
    level = SEVERITY_TO_LEVEL.get(diagnostic.severity, "warning")
    result = OrderedDict()
    result["ruleId"] = code
    result["level"] = level
    result["message"] = OrderedDict((("text", diagnostic.message),))
    location = _location(diagnostic)
    if location is not None:
        result["locations"] = [location]
    if diagnostic.hint:
        result["properties"] = OrderedDict((("hint", diagnostic.hint),))
    return result


def sarif_document(diagnostics):
    """Build a full SARIF 2.1.0 log (as a JSON-serializable `OrderedDict`)
    from an already-filtered list of `Diagnostic` objects.

    Rule metadata is deduplicated by code: each distinct code contributes
    exactly one `tool.driver.rules[]` entry, in first-seen order, so a file
    with many instances of the same diagnostic code does not repeat its
    rule metadata once per instance.
    """
    from . import __version__

    rules_by_code = OrderedDict()
    results = []
    for diagnostic in diagnostics:
        code = diagnostic.code or ""
        if code not in rules_by_code:
            rules_by_code[code] = _rule(code, diagnostic_category(diagnostic))
        results.append(_result(diagnostic))

    driver = OrderedDict(
        (
            ("name", TOOL_NAME),
            ("version", __version__),
            ("informationUri", TOOL_INFORMATION_URI),
            ("rules", list(rules_by_code.values())),
        )
    )
    run = OrderedDict(
        (
            ("tool", OrderedDict((("driver", driver),))),
            ("results", results),
        )
    )
    return OrderedDict(
        (
            ("$schema", SARIF_SCHEMA_URI),
            ("version", SARIF_VERSION),
            ("runs", [run]),
        )
    )


def render_sarif(diagnostics):
    return json.dumps(sarif_document(diagnostics), ensure_ascii=False, indent=2) + "\n"
