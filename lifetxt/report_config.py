"""Configuration metadata for named periodic Markdown reports."""

from __future__ import annotations


def install_report_config_registry():
    """Extend the authoritative registry with report-profile metadata once."""
    from . import config_registry

    if getattr(config_registry, "_lifetxt_report_config_installed", False):
        return

    entry = config_registry._entry
    entries = (
        (
            "reports",
            entry(
                "object",
                None,
                "Named periodic Markdown report profiles used by `lifetxt report`.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.period",
            entry(
                "string",
                None,
                "Calendar period for the report profile.",
                required=True,
                allowed=["daily", "weekly", "monthly"],
                since="unreleased",
            ),
        ),
        (
            "reports.*.output",
            entry(
                "string",
                None,
                "Generated Markdown path template. Required by `report run`; relative paths resolve from the config file directory.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.title",
            entry(
                "string",
                None,
                "Optional title passed to the existing Markdown share renderer.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.project",
            entry(
                "string",
                None,
                "Optional project filter passed to the existing share renderer.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.type",
            entry(
                "string",
                None,
                "Optional life.txt item type filter passed to the existing share renderer.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.tag",
            entry(
                "string",
                None,
                "Optional tag filter passed to the existing share renderer.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.open",
            entry(
                "boolean",
                False,
                "When true, include only unfinished workflow items.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.mode",
            entry(
                "string",
                "replace",
                "Generated-file behavior for `report run`.",
                allowed=["replace", "create", "append"],
                since="unreleased",
            ),
        ),
        (
            "reports.*.frontmatter",
            entry(
                "boolean",
                True,
                "Prepend lifetxt report metadata as YAML-compatible frontmatter.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.sections",
            entry(
                "array",
                None,
                "Report v2: ordered list of {type, ...options} section providers. "
                "Presence of this key opts the profile into Report v2 composition "
                "instead of the v1 `share --format markdown` delegation.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.format",
            entry(
                "string",
                "markdown",
                "Report v2 output format.",
                allowed=["markdown", "json", "html"],
                since="unreleased",
            ),
        ),
        (
            "reports.*.audience",
            entry(
                "string",
                "private",
                "Report v2 disclosure boundary. `external` restricts sections to "
                "aggregate-only types and redacts verbatim content from their data.",
                allowed=["private", "external"],
                since="unreleased",
            ),
        ),
        (
            "reports.*.compare",
            entry(
                "string",
                None,
                "Report v2: attach a numeric diff against the immediately previous period.",
                allowed=["previous"],
                since="unreleased",
            ),
        ),
        (
            "reports.*.email",
            entry(
                "object",
                None,
                "Deliver this report by email via `lifetxt report send`; requires `to`.",
                since="unreleased",
            ),
        ),
        (
            "reports.*.scope",
            entry(
                "object",
                None,
                "Report v2: report-wide filter (project/tag/type/status/person/open) "
                "applied once to the parsed item set before any section provider runs. "
                "Legacy top-level project/type/tag/open are accepted as compatibility "
                "aliases into scope; a conflicting value in both forms fails loudly.",
                since="unreleased",
            ),
        ),
    )
    for key, metadata in entries:
        config_registry.CONFIG_REGISTRY[key] = metadata
    config_registry._lifetxt_report_config_installed = True
