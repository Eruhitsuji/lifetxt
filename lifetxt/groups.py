"""Group directory and recipient resolution for messaging.

A group is a named, config-defined set of members. Members may be people, teams
(from the existing ``teams`` config), or other groups, so groups nest. Expansion
is deterministic, removes duplicates and disabled members, and detects cycles
rather than looping forever. Both the original references and the fully resolved
recipient set are returned so an authored message stays readable while an audit
trail keeps the exact set that was targeted.

Groups live under the ``groups`` configuration section and follow
``group-v1.schema.json``:

    "groups": {
      "oncall": { "members": ["alice", "bob"], "disabled_members": ["bob"] },
      "eng":    { "members": ["oncall", "team:platform"] }
    }
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .config import config_section, config_team_members


GROUP_VERSION = "1"


def diagnostic(severity, code, message, hint="", ref=None):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("hint", hint),
            ("ref", ref),
        )
    )


def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v)]
    return [str(value)]


def group_directory(config):
    """Return ``name -> normalized group`` from the ``groups`` config section."""
    directory = OrderedDict()
    for name, definition in config_section(config, "groups").items():
        if isinstance(definition, dict):
            members = _as_list(definition.get("members"))
            disabled = _as_list(definition.get("disabled_members"))
            visibility = definition.get("visibility")
            aliases = _as_list(definition.get("aliases"))
        else:
            members = _as_list(definition)
            disabled = []
            visibility = None
            aliases = []
        directory[str(name)] = OrderedDict(
            (
                ("group_version", GROUP_VERSION),
                ("name", str(name)),
                ("members", members),
                ("disabled_members", disabled),
                ("visibility", visibility),
                ("aliases", aliases),
            )
        )
    return directory


def _alias_map(directory):
    aliases = OrderedDict()
    for name, group in directory.items():
        aliases[name] = name
        for alias in group["aliases"]:
            aliases[alias] = name
    return aliases


def _strip_prefix(ref):
    """Split an optional ``kind:name`` prefix (team:, group:, user:)."""
    text = str(ref)
    for prefix in ("group:", "team:", "user:", "person:"):
        if text.startswith(prefix):
            return prefix[:-1], text[len(prefix):]
    return None, text


def expand_group(config, name, _seen=None, _directory=None, _aliases=None,
                 _teams=None, diagnostics=None):
    """Expand one group into an ordered, de-duplicated member list."""
    directory = _directory if _directory is not None else group_directory(config)
    aliases = _aliases if _aliases is not None else _alias_map(directory)
    teams = _teams if _teams is not None else config_team_members(config)
    diagnostics = diagnostics if diagnostics is not None else []
    seen_groups = _seen if _seen is not None else []

    canonical = aliases.get(name, name)
    if canonical not in directory:
        diagnostics.append(
            diagnostic("error", "G001", "Unknown group %r." % name,
                       "Define it under the groups config section.", name)
        )
        return []
    if canonical in seen_groups:
        cycle = " -> ".join(seen_groups + [canonical])
        diagnostics.append(
            diagnostic("error", "G002", "Group cycle detected: %s." % cycle,
                       "Remove the self-reference from a group's members.", canonical)
        )
        return []

    group = directory[canonical]
    disabled = set(group["disabled_members"])
    result = []
    for member in group["members"]:
        kind, bare = _strip_prefix(member)
        if member in disabled or bare in disabled:
            continue
        if kind == "group" or (kind is None and aliases.get(bare, bare) in directory):
            nested = expand_group(
                config, bare, seen_groups + [canonical], directory, aliases,
                teams, diagnostics,
            )
            _extend_unique(result, nested)
        elif kind == "team" or (kind is None and bare in teams):
            _extend_unique(result, teams.get(bare, []))
        else:
            _extend_unique(result, [bare])
    # Apply disabled filter to fully-resolved people as well.
    return [person for person in result if person not in disabled]


def _extend_unique(target, values):
    for value in values:
        if value not in target:
            target.append(value)


def resolve_recipients(config, references):
    """Resolve mixed person/team/group references into a recipient set.

    Returns a dict with the original references, the deterministic resolved
    recipient list, a per-reference expansion map, and typed diagnostics.
    """
    directory = group_directory(config)
    aliases = _alias_map(directory)
    teams = config_team_members(config)
    diagnostics = []
    references = _as_list(references)

    resolved = []
    expansion = OrderedDict()
    for ref in references:
        kind, bare = _strip_prefix(ref)
        if kind == "group" or (kind is None and aliases.get(bare, bare) in directory):
            members = expand_group(config, bare, None, directory, aliases, teams, diagnostics)
            if not members:
                diagnostics.append(
                    diagnostic("warning", "G003", "Group %r resolved to no recipients." % bare,
                               "Check members and disabled_members.", ref)
                )
            expansion[ref] = members
            _extend_unique(resolved, members)
        elif kind == "team" or (kind is None and bare in teams):
            members = teams.get(bare, [])
            expansion[ref] = list(members)
            _extend_unique(resolved, members)
        else:
            expansion[ref] = [bare]
            _extend_unique(resolved, [bare])

    return OrderedDict(
        (
            ("references", references),
            ("recipients", resolved),
            ("expansion", expansion),
            ("count", len(resolved)),
            ("diagnostics", diagnostics),
        )
    )


def validate_groups(config):
    """Validate every group: unknown members, cycles, and empty groups."""
    directory = group_directory(config)
    aliases = _alias_map(directory)
    teams = config_team_members(config)
    rows = []
    for name in directory:
        diagnostics = []
        members = expand_group(config, name, None, directory, aliases, teams, diagnostics)
        rows.extend(diagnostics)
        if not members and not diagnostics:
            rows.append(
                diagnostic("warning", "G003", "Group %r is empty." % name,
                           "Add members or remove the group.", name)
            )
    return _dedupe(rows)


def _dedupe(rows):
    seen = set()
    result = []
    for row in rows:
        key = (row["code"], row["ref"], row["message"])
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def group_summaries(config):
    directory = group_directory(config)
    aliases = _alias_map(directory)
    teams = config_team_members(config)
    summaries = []
    for name, group in directory.items():
        diagnostics = []
        members = expand_group(config, name, None, directory, aliases, teams, diagnostics)
        summaries.append(
            OrderedDict(
                (
                    ("name", name),
                    ("direct_members", len(group["members"])),
                    ("resolved_members", len(members)),
                    ("disabled", len(group["disabled_members"])),
                    ("visibility", group["visibility"]),
                    ("ok", not any(d["severity"] == "error" for d in diagnostics)),
                )
            )
        )
    return summaries
