"""Starter presets for `lifetxt init` (#637).

A preset is a small, deterministic set of `# Section` comment headings
inserted around the existing single starter task -- plain Format 1.0
comment lines, not a new grammar, parser, or writer. ``minimal`` (the
default) is intentionally empty, so omitting ``--preset`` produces exactly
the same `init` output this command already generated before this feature
existed.

Both interactive and non-interactive `init` call :func:`render_life_text`,
so there is exactly one place that decides what a preset's starter file
looks like.
"""

from __future__ import unicode_literals

from collections import OrderedDict


DEFAULT_PRESET = "minimal"

#: preset name -> ordered `# Section` heading lines. The first heading (if
#: any) hosts the existing starter task; the rest are left empty for the
#: user to fill in. Content is deliberately small: comments and blank
#: sections, never fabricated sample records.
PRESET_SECTIONS = OrderedDict(
    (
        ("minimal", ()),
        ("personal", ("# Tasks", "# Notes")),
        ("student", ("# Tasks", "# Classes / Events", "# Deadlines", "# Notes")),
        ("work", ("# Tasks", "# Meetings", "# Projects", "# Notes")),
        (
            "research",
            ("# Tasks", "# Meetings", "# Experiments", "# Research Notes"),
        ),
    )
)


def preset_names():
    return tuple(PRESET_SECTIONS.keys())


def validate_preset(name):
    if name not in PRESET_SECTIONS:
        raise ValueError(
            "Unknown starter preset: %r. Available presets: %s"
            % (name, ", ".join(preset_names()))
        )


def render_life_text(name, timezone_val, project, today, preset=DEFAULT_PRESET):
    """Build the complete starter `life.txt` text for one preset.

    ``today`` is the already-resolved ISO date string for the starter
    task's ``due:``. Returns the full file text, newline-terminated.
    """
    validate_preset(preset)
    sections = PRESET_SECTIONS[preset]

    lines = ["#! self: %s" % name, "#! timezone: %s" % timezone_val]
    if project:
        lines.append("#! project: %s" % project)
    lines.append("")

    project_detail = (" project:%s" % project) if project else ""
    starter_task = "[ ] T First_Task%s due:%s" % (project_detail, today)

    if not sections:
        lines.append(starter_task)
    else:
        lines.append(sections[0])
        lines.append("")
        lines.append(starter_task)
        for heading in sections[1:]:
            lines.append("")
            lines.append(heading)

    return "\n".join(lines) + "\n"
