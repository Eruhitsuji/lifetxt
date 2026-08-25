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
    )
    for key, metadata in entries:
        config_registry.CONFIG_REGISTRY[key] = metadata
    config_registry._lifetxt_report_config_installed = True
