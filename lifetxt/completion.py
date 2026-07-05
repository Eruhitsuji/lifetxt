import os
import sys

from .model import KNOWN_KEYS, STATUS_ALIASES, TYPE_ALIASES, VALID_STATUSES, VALID_TYPES


COMMANDS = (
    "check",
    "ids",
    "links",
    "sources",
    "to-json",
    "to-jsonl",
    "to-csv",
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
    "--format": "text life html json jsonl markdown table",
    "--window": "1h 2h 6h 1d 3d 1w 2w 1mo 3mo 1y",
    "--around": "now today",
}


def cmd_completion(args):
    if args.completion_command == "install":
        output = install_instructions(args.shell)
    elif args.completion_command == "bash":
        output = bash_completion()
    elif args.completion_command == "zsh":
        output = zsh_completion()
    elif args.completion_command == "fish":
        output = fish_completion()
    else:
        raise ValueError("completion requires bash, zsh, fish, or install.")

    if getattr(args, "output", None):
        _write_text(args.output, output)
    else:
        sys.stdout.write(output)
    return 0


def bash_completion():
    commands = " ".join(COMMANDS)
    options = " ".join(sorted(set(COMMON_OPTIONS + _all_options())))
    type_values = OPTION_VALUES["--type"]
    status_values = OPTION_VALUES["--status"]
    format_values = OPTION_VALUES["--format"]
    window_values = OPTION_VALUES["--window"]
    around_values = OPTION_VALUES["--around"]
    return """# lifetxt bash completion
_lifetxt_completion() {
  local cur prev
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"

  case "$prev" in
    --type) COMPREPLY=( $(compgen -W "%(type_values)s" -- "$cur") ); return 0 ;;
    --status) COMPREPLY=( $(compgen -W "%(status_values)s" -- "$cur") ); return 0 ;;
    --format) COMPREPLY=( $(compgen -W "%(format_values)s" -- "$cur") ); return 0 ;;
    --window) COMPREPLY=( $(compgen -W "%(window_values)s" -- "$cur") ); return 0 ;;
    --around) COMPREPLY=( $(compgen -W "%(around_values)s" -- "$cur") ); return 0 ;;
  esac

  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "%(options)s" -- "$cur") )
    return 0
  fi

  if [[ $COMP_CWORD -le 1 ]]; then
    COMPREPLY=( $(compgen -W "%(commands)s" -- "$cur") )
    return 0
  fi

  COMPREPLY=( $(compgen -f -X '!*.txt' -- "$cur") $(compgen -f -X '!*.life.txt' -- "$cur") $(compgen -f -X '!*_life.txt' -- "$cur") )
}
complete -F _lifetxt_completion lifetxt
""" % {
        "commands": commands,
        "options": options,
        "type_values": type_values,
        "status_values": status_values,
        "format_values": format_values,
        "window_values": window_values,
        "around_values": around_values,
    }


def zsh_completion():
    commands = " ".join(COMMANDS)
    options = " ".join(sorted(set(COMMON_OPTIONS + _all_options())))
    type_values = OPTION_VALUES["--type"]
    status_values = " ".join("'%s'" % value for value in VALID_STATUSES)
    status_words = " ".join(_STATUS_ALIAS_WORDS)
    format_values = OPTION_VALUES["--format"]
    window_values = OPTION_VALUES["--window"]
    around_values = OPTION_VALUES["--around"]
    return """#compdef lifetxt
# lifetxt zsh completion
_lifetxt() {
  local -a commands options
  commands=(%(commands)s)
  options=(%(options)s)
  case "$words[CURRENT-1]" in
    --type) _values 'type' %(type_values)s; return ;;
    --status) _values 'status' %(status_words)s %(status_values)s; return ;;
    --format) _values 'format' %(format_values)s; return ;;
    --window) _values 'window' %(window_values)s; return ;;
    --around) _values 'around' %(around_values)s; return ;;
  esac
  if [[ CURRENT -eq 2 ]]; then
    _values 'command' $commands
  elif [[ "$PREFIX" == -* ]]; then
    _values 'option' $options
  else
    _files -g '*.txt'
  fi
}
_lifetxt "$@"
""" % {
        "commands": commands,
        "options": options,
        "type_values": type_values,
        "status_words": status_words,
        "status_values": status_values,
        "format_values": format_values,
        "window_values": window_values,
        "around_values": around_values,
    }


def fish_completion():
    lines = ["# lifetxt fish completion"]
    for command in COMMANDS:
        lines.append("complete -c lifetxt -f -n '__fish_use_subcommand' -a '%s'" % command)
    for option in sorted(set(COMMON_OPTIONS + _all_options())):
        if option.startswith("--"):
            lines.append("complete -c lifetxt -l %s" % option[2:])
    status_values = " ".join(['"%s"' % value for value in VALID_STATUSES])
    lines.append("complete -c lifetxt -l type -a '%s'" % OPTION_VALUES["--type"])
    lines.append("complete -c lifetxt -l status -a '%s %s'" % (" ".join(_STATUS_ALIAS_WORDS), status_values))
    lines.append("complete -c lifetxt -l format -a '%s'" % OPTION_VALUES["--format"])
    lines.append("complete -c lifetxt -l window -a '%s'" % OPTION_VALUES["--window"])
    lines.append("complete -c lifetxt -l around -a '%s'" % OPTION_VALUES["--around"])
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
    "--pretty",
    "--output",
    "--append",
    "--update",
    "--line",
    "--match-id",
    "--action",
    "--tool",
    "--preview",
    "--no-preview",
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
    "--path",
)


def _all_options():
    return tuple(_unique_ordered(list(_STRUCTURAL_OPTIONS) + ["--%s" % key for key in KNOWN_KEYS]))


def _write_text(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
