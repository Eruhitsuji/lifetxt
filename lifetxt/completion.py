"""Shell completion scripts.

Everything a shell offers is derived from `lifetxt/cli.py`'s argparse tree and
from `lifetxt/model.py`, so a new command or flag shows up in completion the
moment it exists rather than when someone remembers to update a list here.

Three kinds of candidate are produced:

* **Commands** - the subparser names, with their help text as the description.
* **Options** - scoped to the command being typed. Offering every flag in the
  program for every command produced hundreds of wrong candidates.
* **Values** - the arguments a flag or positional takes. Static sets live in
  `OPTION_VALUES`; the ones that depend on the user's file (`state`, project,
  tag, person, id) are fetched at completion time via `completion values`.
"""

import os
import sys

from .atomic import atomic_write_text
from .model import KNOWN_KEYS, STATUS_ALIASES, TYPE_ALIASES, VALID_STATUSES, VALID_TYPES
from .presence import COMMON_STATES


COMMANDS = (
    "check",
    "ids",
    "links",
    "sources",
    "to-json",
    "to-jsonl",
    "to-csv",
    "demo",
    "markdown",
    "import-ics",
    "sync-ics",
    "filter",
    "from-json",
    "from-jsonl",
    "from-csv",
    "status",
    "notify",
    "agenda",
    "assist",
    "archive",
    "quick",
    "done",
    "files",
    "batch",
    "summary",
    "init",
    "doctor",
    "assign",
    "health",
    "inbox",
    "cleanup",
    "undo",
    "review",
    "who",
    "search",
    "snapshot",
    "lint",
    "diff",
    "plot",
    "export-heatmap",
    "migrate",
    "from-markdown",
    "deps",
    "tag",
    "watch",
    "encrypt",
    "decrypt",
    "share",
    "digest",
    "template",
    "tui",
    "fzf",
    "timer",
    "stats",
    "git-hook",
    "completion",
    "serve",
    "config",
)

COMMON_OPTIONS = (
    "--config",
    "--help",
)


def _unique_ordered(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


# Derived from lifetxt/model.py so completion candidates stay in sync with
# the canonical type/status alias and detail-key definitions instead of a
# hand-maintained, easily stale copy.
_TYPE_ALIAS_WORDS = _unique_ordered(name for name in TYPE_ALIASES if len(name) > 1)
_STATUS_ALIAS_WORDS = _unique_ordered(name for name in STATUS_ALIASES if len(name) > 1)

OPTION_VALUES = {
    "--type": " ".join(_TYPE_ALIAS_WORDS + list(VALID_TYPES)),
    "--status": " ".join(_STATUS_ALIAS_WORDS + list(VALID_STATUSES)),
    "--format": "text life html json jsonl markdown table csv mermaid dot svg png",
    "--window": "1h 2h 6h 1d 3d 1w 2w 1mo 3mo 1y",
    "--around": "now today",
    "--preset": "ics markdown todoist github",
    "--algorithm": "auto xsk aesgcm",
    "--theme": "auto dark light mono",
    "--keymap": "prompt vim arrows",
    # `state:` is free-form in the format, so this is the documented set from
    # presence.py rather than a closed list. `completion values --kind state`
    # adds whatever the user's own file already uses.
    "--state": " ".join(COMMON_STATES),
    "--glyphs": "auto unicode ascii",
    "--order": "asc desc",
    "--sort": "line time title type status source",
    "--visibility": "public team private",
    "--shell": "bash zsh fish powershell",
    "--group": "project tag type status person day week month",
    "--interval": "day week month",
    "--action": "open edit copy print",
    "--tool": "fzf peco",
}

#: Positional arguments worth completing, keyed by command. The value is the
#: `OPTION_VALUES` key whose candidates apply to the first positional.
#: `state busy` is the form people actually type, so completing only `--state`
#: would miss the common case.
COMMAND_POSITIONAL_VALUES = {
    "state": "--state",
    "s": "--state",
    "start": "--state",
    "completion": None,  # handled by the subcommand list below
}

#: Commands whose first positional is a fixed word list rather than a path.
COMMAND_SUBCOMMANDS = {
    "completion": ("bash", "zsh", "fish", "powershell", "install", "values"),
    "timer": ("start", "stop", "status", "cancel"),
    "git-hook": ("install", "uninstall", "status"),
    "config": ("show", "path", "init"),
}

#: Kinds that `completion values` can read out of a life.txt file.
VALUE_KINDS = (
    "state",
    "project",
    "tag",
    "person",
    "id",
    "type",
    "status",
    "context",
    "priority",
    "key",
    "team",
    "service",
    "channel",
)

#: Detail keys whose values feed each kind. One place to look when adding a
#: kind, and the reason `person` spans every people-shaped key at once.
_KIND_DETAIL_KEYS = {
    "state": ("state",),
    "project": ("project",),
    "tag": ("tag",),
    "id": ("id",),
    "context": ("context",),
    "priority": ("priority",),
    "team": ("team",),
    "service": ("service",),
    "channel": ("channel",),
    "person": (
        "person",
        "owner",
        "assignee",
        "attendee",
        "sender",
        "recipient",
        "user",
    ),
}

#: Values worth offering before a file contains any, so a new file still
#: completes usefully. Merged ahead of the file's own values.
_KIND_BUILTINS = {
    "state": COMMON_STATES,
    "priority": ("high", "medium", "low"),
}


def candidates(kind, prefix="", items=None, paths=None, limit=None):
    """Ranked completion candidates for one kind, shared by every surface.

    `items` lets a caller that already holds parsed records (the Web API and
    the TUI both do) avoid re-reading the file; `paths` is the CLI's route.
    Ranking puts prefix matches ahead of substring matches so typing `bu`
    offers `busy` before `debug`.
    """
    if kind not in VALUE_KINDS:
        raise ValueError(
            "Unknown completion kind %r. Use one of: %s"
            % (kind, ", ".join(VALUE_KINDS))
        )

    if kind == "type":
        pool = _TYPE_ALIAS_WORDS + list(VALID_TYPES)
    elif kind == "status":
        pool = _STATUS_ALIAS_WORDS + list(VALID_STATUSES)
    elif kind == "key":
        pool = sorted(KNOWN_KEYS)
    else:
        found = (
            _values_from_items(items, kind)
            if items is not None
            else _values_from_files(kind, paths)
        )
        pool = _unique_ordered(list(_KIND_BUILTINS.get(kind, ())) + list(found))

    ranked = _rank(pool, prefix)
    if limit is not None and limit >= 0:
        ranked = ranked[:limit]
    return ranked


def _rank(pool, prefix):
    """Prefix matches first, then substring matches, each keeping pool order."""
    needle = str(prefix or "").strip().lower()
    if not needle:
        return list(pool)

    starts, contains = [], []
    for value in pool:
        lowered = str(value).lower()
        if lowered.startswith(needle):
            starts.append(value)
        elif needle in lowered:
            contains.append(value)
    return starts + contains


def _values_from_items(items, kind):
    values = []
    for item in items or ():
        values.extend(_item_values(item, kind))
    return _unique_ordered(value for value in values if value)


def add_completion_parsers(subparsers, handler):
    """Register the completion command group without owning CLI parsing."""
    completion = subparsers.add_parser(
        "completion",
        help="Generate shell completion scripts.",
    )
    completion_subparsers = completion.add_subparsers(dest="completion_command")
    for shell in ("bash", "zsh", "fish"):
        shell_parser = completion_subparsers.add_parser(
            shell, help="Generate %s completion." % shell
        )
        shell_parser.add_argument(
            "-o", "--output", help="Output file. Defaults to stdout."
        )
        shell_parser.set_defaults(func=handler)
    completion_install = completion_subparsers.add_parser(
        "install", help="Print installation instructions."
    )
    completion_install.add_argument(
        "--shell",
        choices=("bash", "zsh", "fish", "powershell"),
        help="Shell to show instructions for.",
    )
    completion_install.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    completion_install.set_defaults(func=handler)
    completion_values = completion_subparsers.add_parser(
        "values",
        help="Print completion candidates read from a life.txt file.",
    )
    completion_values.add_argument(
        "--kind",
        choices=VALUE_KINDS,
        required=True,
        help="Candidate kind to print, one per line.",
    )
    completion_values.add_argument(
        "path", nargs="*", help="life.txt file(s) to read. Defaults to config paths."
    )
    completion_values.add_argument(
        "-o", "--output", help="Output file. Defaults to stdout."
    )
    completion_values.set_defaults(func=handler)
    return completion


def cmd_completion(args):
    command = args.completion_command
    if command == "install":
        output = install_instructions(args.shell)
    elif command == "bash":
        output = bash_completion()
    elif command == "zsh":
        output = zsh_completion()
    elif command == "fish":
        output = fish_completion()
    elif command == "values":
        output = dynamic_values(
            getattr(args, "kind", None), getattr(args, "path", None)
        )
    else:
        raise ValueError("completion requires bash, zsh, fish, values, or install.")

    if getattr(args, "output", None):
        _write_text(args.output, output)
    else:
        sys.stdout.write(output)
    return 0


def dynamic_values(kind, paths=None):
    """Candidates read from the user's own file, one per line.

    Shells call this while the user is typing, so it must never fail loudly:
    an unreadable or missing file yields the built-in candidates instead of an
    error that would corrupt the completion display.
    """
    if kind not in VALUE_KINDS:
        raise ValueError(
            "completion values --kind must be one of: %s" % ", ".join(VALUE_KINDS)
        )

    if kind == "type":
        return "\n".join(_TYPE_ALIAS_WORDS + list(VALID_TYPES)) + "\n"
    if kind == "status":
        return "\n".join(_STATUS_ALIAS_WORDS + list(VALID_STATUSES)) + "\n"

    found = _values_from_files(kind, paths)
    if kind == "state":
        # The documented states come first so a fresh file still completes.
        found = _unique_ordered(list(COMMON_STATES) + found)
    return ("\n".join(found) + "\n") if found else ""


def _values_from_files(kind, paths):
    try:
        from .config import config_paths, load_config
        from .parser import parse_text
        from .paths import expand_paths
    except Exception:
        return []

    try:
        candidates = (
            list(paths) if paths else list(config_paths(load_config(None)) or [])
        )
        if not candidates:
            candidates = ["life.txt"]
        resolved = expand_paths(candidates)
    except Exception:
        return []

    values = []
    for path in resolved:
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                # parse_text returns (items, errors); parse errors elsewhere in
                # the file must not stop the valid lines from completing.
                items = parse_text(handle.read())[0]
        except Exception:
            continue
        for item in items:
            values.extend(_item_values(item, kind))
    return _unique_ordered(value for value in values if value)


def _item_values(item, kind):
    details = getattr(item, "details", None) or {}
    values = []
    for key in _KIND_DETAIL_KEYS.get(kind, ()):
        values.extend(_detail_list(details, key))
    return values


def _detail_list(details, key):
    value = details.get(key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(entry) for entry in value]
    return [str(value)]


def _value_case_entries():
    """(`option`, `candidates`) pairs shared by the generated shell scripts."""
    return sorted(OPTION_VALUES.items())


def bash_completion():
    commands = " ".join(_command_names())
    options = " ".join(sorted(set(COMMON_OPTIONS + _all_options())))

    value_cases = "\n".join(
        '    %s) COMPREPLY=( $(compgen -W "%s" -- "$cur") ); return 0 ;;'
        % (option, values)
        for option, values in _value_case_entries()
    )

    # Per-command options. Without this every command offered every flag in
    # the program, which buried the handful that actually applied.
    command_cases = "\n".join(
        '    %s) opts="%s" ;;' % (name, " ".join(_command_options(name)))
        for name in _command_names()
        if _command_options(name)
    )

    subcommand_cases = "\n".join(
        '    %s) COMPREPLY=( $(compgen -W "%s" -- "$cur") ); return 0 ;;'
        % (name, " ".join(words))
        for name, words in sorted(COMMAND_SUBCOMMANDS.items())
    )

    positional_cases = "\n".join(
        '    %s) COMPREPLY=( $(compgen -W "$(%s)" -- "$cur") ); return 0 ;;'
        % (name, _dynamic_call(COMMAND_POSITIONAL_VALUES[name]))
        for name in sorted(COMMAND_POSITIONAL_VALUES)
        if COMMAND_POSITIONAL_VALUES[name]
    )

    return """# lifetxt bash completion
_lifetxt_values() {
  # Candidates from the user's own file, with the built-in list as fallback.
  lifetxt completion values --kind "$1" 2>/dev/null
}
_lifetxt_completion() {
  local cur prev cmd opts i
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"

  cmd=""
  for ((i=1; i<COMP_CWORD; i++)); do
    case "${COMP_WORDS[i]}" in
      -*) ;;
      *) cmd="${COMP_WORDS[i]}"; break ;;
    esac
  done

  case "$prev" in
%(value_cases)s
    --project) COMPREPLY=( $(compgen -W "$(_lifetxt_values project)" -- "$cur") ); return 0 ;;
    --tag|--tag-all|--exclude-tag) COMPREPLY=( $(compgen -W "$(_lifetxt_values tag)" -- "$cur") ); return 0 ;;
    --id|--match-id) COMPREPLY=( $(compgen -W "$(_lifetxt_values id)" -- "$cur") ); return 0 ;;
    --person|--owner|--assignee|--attendee|--sender|--recipient|--user) COMPREPLY=( $(compgen -W "$(_lifetxt_values person)" -- "$cur") ); return 0 ;;
  esac

  if [[ $COMP_CWORD -le 1 ]]; then
    COMPREPLY=( $(compgen -W "%(commands)s" -- "$cur") )
    return 0
  fi

  if [[ "$cur" == -* ]]; then
    opts=""
    case "$cmd" in
%(command_cases)s
    esac
    [[ -z "$opts" ]] && opts="%(options)s"
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    return 0
  fi

  # The word right after the command: a fixed subcommand or a value list.
  if [[ "${COMP_WORDS[COMP_CWORD-1]}" == "$cmd" ]]; then
    case "$cmd" in
%(subcommand_cases)s
%(positional_cases)s
    esac
  fi

  COMPREPLY=( $(compgen -f -X '!*.txt' -- "$cur") $(compgen -f -X '!*.life.txt' -- "$cur") $(compgen -f -X '!*_life.txt' -- "$cur") )
}
complete -F _lifetxt_completion lifetxt
""" % {
        "commands": commands,
        "options": options,
        "value_cases": value_cases,
        "command_cases": command_cases,
        "subcommand_cases": subcommand_cases,
        "positional_cases": positional_cases,
    }


def _dynamic_call(option_key):
    kind = option_key.lstrip("-")
    return "_lifetxt_values %s" % kind


def zsh_completion():
    commands = " ".join(
        "'%s:%s'" % (name, _command_help(name).replace(":", " ").replace("'", ""))
        for name in _command_names()
    )
    options = " ".join(sorted(set(COMMON_OPTIONS + _all_options())))

    value_cases = "\n".join(
        "    %s) _values '%s' %s; return ;;"
        % (option, option.lstrip("-"), " ".join(values.split()))
        for option, values in _value_case_entries()
    )
    command_cases = "\n".join(
        "      %s) _values 'option' %s; return ;;"
        % (name, " ".join(_command_options(name)))
        for name in _command_names()
        if _command_options(name)
    )
    subcommand_cases = "\n".join(
        "      %s) _values 'subcommand' %s; return ;;" % (name, " ".join(words))
        for name, words in sorted(COMMAND_SUBCOMMANDS.items())
    )
    positional_cases = "\n".join(
        "      %s) _values 'state' ${(f)\"$(lifetxt completion values --kind state 2>/dev/null)\"}; return ;;"
        % name
        for name in sorted(COMMAND_POSITIONAL_VALUES)
        if COMMAND_POSITIONAL_VALUES[name]
    )

    return """#compdef lifetxt
# lifetxt zsh completion
_lifetxt() {
  local -a commands options
  local cmd i
  commands=(%(commands)s)
  options=(%(options)s)

  cmd=""
  for (( i = 2; i < CURRENT; i++ )); do
    case "$words[i]" in
      -*) ;;
      *) cmd="$words[i]"; break ;;
    esac
  done

  case "$words[CURRENT-1]" in
%(value_cases)s
    --project) _values 'project' ${(f)"$(lifetxt completion values --kind project 2>/dev/null)"}; return ;;
    --tag|--tag-all|--exclude-tag) _values 'tag' ${(f)"$(lifetxt completion values --kind tag 2>/dev/null)"}; return ;;
    --id|--match-id) _values 'id' ${(f)"$(lifetxt completion values --kind id 2>/dev/null)"}; return ;;
    --person|--owner|--assignee|--attendee|--sender|--recipient|--user) _values 'person' ${(f)"$(lifetxt completion values --kind person 2>/dev/null)"}; return ;;
  esac

  if [[ CURRENT -eq 2 ]]; then
    _describe 'command' commands
  elif [[ "$PREFIX" == -* ]]; then
    case "$cmd" in
%(command_cases)s
    esac
    _values 'option' $options
  elif [[ "$words[CURRENT-1]" == "$cmd" ]]; then
    case "$cmd" in
%(subcommand_cases)s
%(positional_cases)s
    esac
    _files -g '*.txt'
  else
    _files -g '*.txt'
  fi
}
_lifetxt "$@"
""" % {
        "commands": commands,
        "options": options,
        "value_cases": value_cases,
        "command_cases": command_cases,
        "subcommand_cases": subcommand_cases,
        "positional_cases": positional_cases,
    }


def fish_completion():
    lines = ["# lifetxt fish completion"]
    for command in _command_names():
        lines.append(
            "complete -c lifetxt -f -n '__fish_use_subcommand' -a '%s' -d '%s'"
            % (command, _command_help(command).replace("'", ""))
        )

    # Options are offered only under the commands that accept them.
    for command in _command_names():
        command_options = _command_options(command)
        if not command_options:
            continue
        for option in command_options:
            lines.append(
                "complete -c lifetxt -n '__fish_seen_subcommand_from %s' -l %s"
                % (command, option[2:])
            )

    for option, values in _value_case_entries():
        lines.append("complete -c lifetxt -l %s -a '%s'" % (option[2:], values))

    for name, words in sorted(COMMAND_SUBCOMMANDS.items()):
        lines.append(
            "complete -c lifetxt -f -n '__fish_seen_subcommand_from %s' -a '%s'"
            % (name, " ".join(words))
        )

    for name in sorted(COMMAND_POSITIONAL_VALUES):
        if not COMMAND_POSITIONAL_VALUES[name]:
            continue
        lines.append(
            "complete -c lifetxt -f -n '__fish_seen_subcommand_from %s' "
            "-a '(lifetxt completion values --kind state 2>/dev/null)'" % name
        )

    for kind, option_names in (
        ("project", ("project",)),
        ("tag", ("tag", "tag-all", "exclude-tag")),
        ("id", ("id", "match-id")),
        (
            "person",
            ("person", "owner", "assignee", "attendee", "sender", "recipient", "user"),
        ),
    ):
        for option_name in option_names:
            lines.append(
                "complete -c lifetxt -l %s -a '(lifetxt completion values --kind %s 2>/dev/null)'"
                % (option_name, kind)
            )

    return "\n".join(lines) + "\n"


def install_instructions(shell):
    if shell == "bash":
        return """# bash
source <(lifetxt completion bash)
# or add this to ~/.bashrc:
echo 'source <(lifetxt completion bash)' >> ~/.bashrc
"""
    if shell == "zsh":
        return """# zsh
mkdir -p ~/.zfunc
lifetxt completion zsh > ~/.zfunc/_lifetxt
echo 'fpath=(~/.zfunc $fpath)' >> ~/.zshrc
echo 'autoload -U compinit && compinit' >> ~/.zshrc
"""
    if shell == "fish":
        return """# fish
mkdir -p ~/.config/fish/completions
lifetxt completion fish > ~/.config/fish/completions/lifetxt.fish
"""
    return """# bash
source <(lifetxt completion bash)

# zsh
lifetxt completion zsh > ~/.zfunc/_lifetxt

# fish
lifetxt completion fish > ~/.config/fish/completions/lifetxt.fish

# powershell
lifetxt completion powershell -o $HOME\\Documents\\PowerShell\\lifetxt-completion.ps1
"""


# Structural CLI flags that are not life.txt detail keys (those come from
# lifetxt/model.py's KNOWN_KEYS below) and so cannot be derived from model.py.
_STRUCTURAL_OPTIONS = (
    "--open",
    "--status",
    "--type",
    "--project",
    "--tag",
    "--tag-all",
    "--exclude-tag",
    "--user",
    "--team",
    "--person",
    "--owner",
    "--assignee",
    "--attendee",
    "--sender",
    "--recipient",
    "--detail",
    "--text",
    "--after",
    "--before",
    "--from",
    "--to",
    "--around",
    "--window",
    "--width",
    "--limit",
    "--canonical",
    "--format",
    "--preset",
    "--algorithm",
    "--pretty",
    "--output",
    "--occurrences",
    "--append",
    "--update",
    "--line",
    "--match-id",
    "--add-detail",
    "--remove-detail",
    "--action",
    "--tool",
    "--preview",
    "--no-preview",
    "--no-check",
    "--no-completion",
    "--body-file",
    "--body-stdin",
    "--rrule",
    "--id",
    "--repo-dir",
    "--files",
    "--force",
    "--field",
    "--week",
    "--month",
    "--title",
    "--url-env",
    "--key-env",
    "--key-file",
    "--dry-run",
    "--backup",
    "--yes",
    "--name",
    "--timezone",
    "--config-output",
    "--regex",
    "--in",
    "--highlight",
    "--count",
    "--compare",
    "--group",
    "--interval",
    "--clear",
    "--timestamp",
    "--notify",
    "--old",
    "--new",
    "--migration",
    "--merge-existing",
    "--soft-delete-missing",
    "--path",
)


def _all_options():
    detail_options = []
    for key in KNOWN_KEYS:
        detail_options.append("--%s" % key)
        if "_" in key:
            detail_options.append("--%s" % key.replace("_", "-"))
    return tuple(
        _unique_ordered(
            list(_STRUCTURAL_OPTIONS) + list(_parser_long_options()) + detail_options
        )
    )


def _extra_command_names():
    """Commands the entrypoint routes to `extra_cli` instead of the parser.

    They are real, working commands (`next`, `standup`, `invoice`, ...) but
    they never reach `build_parser`, so deriving completion from argparse
    alone silently dropped them from every shell.
    """
    try:
        from .entrypoint import _EXTRA_COMMANDS

        return tuple(sorted(_EXTRA_COMMANDS))
    except Exception:
        return ()


def _command_names():
    names = list(_parser_command_names()) or list(COMMANDS)
    return tuple(_unique_ordered(names + list(_extra_command_names())))


#: Building the parser is expensive and generating a script asks for every
#: command's options, so the tree is built once per process rather than ~70
#: times. Cleared by `_reset_parser_cache` in tests.
_SUBPARSER_CACHE = {}


def _reset_parser_cache():
    _SUBPARSER_CACHE.clear()


def _subparser_map():
    """Command name -> its argparse subparser, or an empty mapping."""
    if "map" in _SUBPARSER_CACHE:
        return _SUBPARSER_CACHE["map"]

    try:
        from . import cli

        parser = cli.build_parser()
    except Exception:
        return {}

    found = {}
    for action in parser._actions:
        if action.__class__.__name__ == "_SubParsersAction":
            found = dict(action.choices)
            break
    _SUBPARSER_CACHE["map"] = found
    return found


def _command_options(name):
    """Long options accepted by one command, including its own subcommands."""
    subparser = _subparser_map().get(name)
    if subparser is None:
        return ()

    options = []

    def walk(arg_parser):
        for action in arg_parser._actions:
            for option in getattr(action, "option_strings", ()):
                if option.startswith("--"):
                    options.append(option)
            if action.__class__.__name__ == "_SubParsersAction":
                for nested in action.choices.values():
                    walk(nested)

    walk(subparser)
    return tuple(_unique_ordered(options + list(COMMON_OPTIONS)))


def _command_help(name):
    """One-line description shown beside a command in zsh and fish menus."""
    subparser = _subparser_map().get(name)
    text = (getattr(subparser, "description", "") or "").strip()
    if not text:
        return name
    first = text.split("\n")[0].strip()
    return first[:70]


def _parser_command_names():
    return tuple(_subparser_map().keys())


def _parser_long_options():
    try:
        from . import cli

        parser = cli.build_parser()
    except Exception:
        return ()

    options = []

    def walk(arg_parser):
        for action in arg_parser._actions:
            for option in getattr(action, "option_strings", ()):
                if option.startswith("--"):
                    options.append(option)
            if action.__class__.__name__ == "_SubParsersAction":
                for subparser in action.choices.values():
                    walk(subparser)

    walk(parser)
    return tuple(_unique_ordered(options))


def _write_text(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    atomic_write_text(path, text)
