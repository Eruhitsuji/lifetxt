import os
import sys


COMMANDS = (
    "check",
    "ids",
    "links",
    "sources",
    "markdown",
    "to-json",
    "to-jsonl",
    "to-csv",
    "from-json",
    "from-jsonl",
    "from-csv",
    "import-ics",
    "sync-ics",
    "filter",
    "status",
    "notify",
    "agenda",
    "assist",
    "serve",
    "config",
    "tui",
    "fzf",
    "timer",
    "stats",
    "git-hook",
    "completion",
)

COMMON_OPTIONS = (
    "--config",
    "--help",
)

OPTION_VALUES = {
    "--type": "task event deadline reminder habit note status message journal T E D R H N S M J",
    "--status": "todo done progress cancel defer pending note [ ] [x] [/] [-] [>] [?] [N]",
    "--format": "text life html json jsonl",
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
    return """#compdef lifetxt
# lifetxt zsh completion
_lifetxt() {
  local -a commands options
  commands=(%(commands)s)
  options=(%(options)s)
  case "$words[CURRENT-1]" in
    --type) _values 'type' task event deadline reminder habit note status message journal T E D R H N S M J; return ;;
    --status) _values 'status' todo done progress cancel defer pending note '[ ]' '[x]' '[/]' '[-]' '[>]' '[?]' '[N]'; return ;;
    --format) _values 'format' text life html json jsonl; return ;;
    --window) _values 'window' 1h 2h 6h 1d 3d 1w 2w 1mo 3mo 1y; return ;;
    --around) _values 'around' now today; return ;;
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
""" % {"commands": commands, "options": options}


def fish_completion():
    lines = ["# lifetxt fish completion"]
    for command in COMMANDS:
        lines.append("complete -c lifetxt -f -n '__fish_use_subcommand' -a '%s'" % command)
    for option in sorted(set(COMMON_OPTIONS + _all_options())):
        if option.startswith("--"):
            lines.append("complete -c lifetxt -l %s" % option[2:])
    lines.append("complete -c lifetxt -l type -a 'task event deadline reminder habit note status message journal T E D R H N S M J'")
    lines.append("complete -c lifetxt -l status -a 'todo done progress cancel defer pending note \"[ ]\" \"[x]\" \"[/]\" \"[-]\" \"[>]\" \"[?]\" \"[N]\"'")
    lines.append("complete -c lifetxt -l format -a 'text life html json jsonl'")
    lines.append("complete -c lifetxt -l window -a '1h 2h 6h 1d 3d 1w 2w 1mo 3mo 1y'")
    lines.append("complete -c lifetxt -l around -a 'now today'")
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


def _all_options():
    return (
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
        "--due",
        "--do",
        "--done",
        "--on",
        "--at",
        "--state",
        "--notify_at",
        "--notify_from",
        "--notify_to",
        "--elapsed",
        "--est",
        "--priority",
        "--loc",
        "--note",
        "--body",
        "--text",
        "--after",
        "--before",
        "--from",
        "--to",
        "--around",
        "--window",
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
    )


def _write_text(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
