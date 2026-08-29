"""Named quick-capture defaults (`capture.presets.<name>`, #594).

A preset is a bounded set of defaults layered under everything explicit a
capture already supports -- config defaults, capture shorthand (``@``/``#``/
``!``/``^``), and explicit CLI flags all still win over a preset value for
the same field. This module only resolves and validates the configuration;
it does not build items, apply shorthand, or write anything -- that stays in
`lifetxt.cli.command_quick`'s existing, single capture implementation.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .config import config_section


#: The only fields a first-slice preset may set. Anything else is rejected
#: rather than silently accepted and ignored.
PRESET_FIELDS = ("type", "status", "project", "tags", "priority")

_SCALAR_FIELDS = ("type", "status", "project", "priority")


def normalize_capture_preset(name, raw):
    """Validate and normalize one preset definition.

    Raises ``ValueError`` naming the preset and the offending field for any
    unknown key, wrong type, or empty value -- configuration mistakes fail
    loudly rather than silently degrading to "no defaults applied".
    """
    if not isinstance(raw, dict):
        raise ValueError(
            "capture.presets.%s must be an object with type/status/project/"
            "tags/priority fields." % name
        )
    unknown = sorted(set(raw) - set(PRESET_FIELDS))
    if unknown:
        raise ValueError(
            "capture.presets.%s has unsupported field(s): %s. Supported "
            "fields are: %s." % (name, ", ".join(unknown), ", ".join(PRESET_FIELDS))
        )

    normalized = OrderedDict()
    for field in _SCALAR_FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "capture.presets.%s.%s must be a non-empty string." % (name, field)
            )
        normalized[field] = value.strip()

    if "tags" in raw:
        tags_value = raw["tags"]
        if not isinstance(tags_value, list) or not tags_value:
            raise ValueError(
                "capture.presets.%s.tags must be a non-empty array of strings." % name
            )
        tags = []
        for tag in tags_value:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(
                    "capture.presets.%s.tags must contain only non-empty strings."
                    % name
                )
            if tag.strip() not in tags:
                tags.append(tag.strip())
        normalized["tags"] = tags

    return normalized


def capture_presets(config):
    """Every configured preset, normalized. Raises loudly on the first
    malformed entry rather than silently dropping it."""
    section = config_section(config, "capture")
    raw_presets = section.get("presets")
    if not raw_presets:
        return OrderedDict()
    if not isinstance(raw_presets, dict):
        raise ValueError("capture.presets must be an object mapping name -> preset.")
    return OrderedDict(
        (name, normalize_capture_preset(name, raw)) for name, raw in raw_presets.items()
    )


def resolve_capture_preset(config, name):
    """Look up and normalize one preset by name.

    Raises ``ValueError`` naming the requested preset and listing every
    available preset name when it is not configured.
    """
    presets = capture_presets(config)
    if name not in presets:
        available = ", ".join(sorted(presets)) if presets else "(none configured)"
        raise ValueError(
            "Unknown capture preset '%s'. Available presets: %s." % (name, available)
        )
    return presets[name]


def install_capture_preset_config_registry():
    """Extend the authoritative registry with capture-preset metadata once.

    Mirrors the wildcard-key pattern `lifetxt.report_config` already
    established for `reports.*.period` -- one shared `explain_key()`
    resolver handles both without any capture-preset-specific lookup code.
    """
    from . import config_registry

    if getattr(config_registry, "_lifetxt_capture_preset_config_installed", False):
        return

    entry = config_registry._entry
    entries = (
        (
            "capture",
            entry(
                "object",
                None,
                "Quick-capture customization, including named presets.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets",
            entry(
                "object",
                None,
                "Named `quick`/`q`/`add` capture presets: capture.presets.NAME "
                "sets type/status/project/tags/priority defaults applied "
                "before capture shorthand and explicit CLI flags, which "
                "still win over the preset for the same field.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets.*.type",
            entry(
                "string",
                None,
                "Default item type for this preset, used only when --type is not given.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets.*.status",
            entry(
                "string",
                None,
                "Default status for this preset, used only when --status is not given.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets.*.project",
            entry(
                "string",
                None,
                "Default project: detail for this preset, used only when no explicit --project or @sigil already set it.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets.*.tags",
            entry(
                "array<string>",
                None,
                "Default tag: details for this preset, merged with (not replaced by) any explicit --tag or #sigil values.",
                since="unreleased",
            ),
        ),
        (
            "capture.presets.*.priority",
            entry(
                "string",
                None,
                "Default priority: detail for this preset, used only when no explicit --priority or !sigil already set it.",
                since="unreleased",
            ),
        ),
    )
    for key, metadata in entries:
        config_registry.CONFIG_REGISTRY[key] = metadata
    config_registry._lifetxt_capture_preset_config_installed = True
