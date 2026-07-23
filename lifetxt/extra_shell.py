"""Shell completion and journal capture commands."""

import argparse
import calendar
import csv
import datetime

from .timezone_policy import today as timezone_today
import hashlib
import io
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unicodedata
from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .atomic import atomic_write_text
from .config import config_paths, config_section, config_user_name, config_write_file, load_config
from .model import Item
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_to_line
from .timeutil import parse_elapsed

from .extra_common import *


def _powershell_completion_script():
    """Native argument completion for PowerShell.

    Everything is derived from `completion.py`, which reads the argparse tree,
    so this cannot drift the way the previous hand-maintained command list did
    (it had lost `rrule`, `tag`, `plot`, and `lint`, and still listed commands
    that no longer existed).
    """
    from .completion import (
        COMMAND_SUBCOMMANDS,
        OPTION_VALUES,
        _command_names,
        _command_options,
        _command_help,
    )

    commands = _command_names()
    command_list = ", ".join("'%s'" % name for name in commands)
    help_map = "\n".join(
        "    '%s' = '%s'" % (name, _command_help(name).replace("'", ""))
        for name in commands
    )
    option_map = "\n".join(
        "    '%s' = @(%s)" % (name, ", ".join("'%s'" % opt for opt in _command_options(name)))
        for name in commands
        if _command_options(name)
    )
    value_map = "\n".join(
        "    '%s' = @(%s)" % (option, ", ".join("'%s'" % word for word in values.split()))
        for option, values in sorted(OPTION_VALUES.items())
    )
    subcommand_map = "\n".join(
        "    '%s' = @(%s)" % (name, ", ".join("'%s'" % word for word in words))
        for name, words in sorted(COMMAND_SUBCOMMANDS.items())
    )

    return """# lifetxt PowerShell native argument completion
$LifetxtCommands = @(%(commands)s)
$LifetxtCommandHelp = @{
%(help_map)s
}
$LifetxtCommandOptions = @{
%(option_map)s
}
$LifetxtOptionValues = @{
%(value_map)s
}
$LifetxtSubcommands = @{
%(subcommand_map)s
}

function Get-LifetxtDynamicValue($kind) {
    # Candidates from the user's own file. Completion must stay silent when
    # the file is missing, so failures fall back to an empty list.
    try { & lifetxt completion values --kind $kind 2>$null } catch { @() }
}

Register-ArgumentCompleter -Native -CommandName lifetxt -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    $tokens = @($commandAst.CommandElements | ForEach-Object { $_.ToString() })
    $result = { param($text, $tip)
        [System.Management.Automation.CompletionResult]::new($text, $text, 'ParameterValue', $tip)
    }

    # Index from 1 explicitly: `$tokens[1..0]` is a *reverse* range in
    # PowerShell, so on a bare `lifetxt ` it would hand back the exe name and
    # the command list would never be offered.
    $command = $null
    for ($i = 1; $i -lt $tokens.Count; $i++) {
        if ($tokens[$i] -notlike '-*') { $command = $tokens[$i]; break }
    }

    $previous = ''
    if ($tokens.Count -ge 2) { $previous = $tokens[$tokens.Count - 1] }
    if ($previous -eq $wordToComplete -and $tokens.Count -ge 3) {
        $previous = $tokens[$tokens.Count - 2]
    }

    # A value for the flag just typed.
    if ($LifetxtOptionValues.ContainsKey($previous)) {
        return $LifetxtOptionValues[$previous] |
            Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { & $result $_ $previous }
    }
    $dynamic = @{
        '--project' = 'project'; '--tag' = 'tag'; '--tag-all' = 'tag';
        '--exclude-tag' = 'tag'; '--id' = 'id'; '--match-id' = 'id';
        '--person' = 'person'; '--owner' = 'person'; '--assignee' = 'person';
        '--attendee' = 'person'; '--sender' = 'person'; '--recipient' = 'person'
    }
    if ($dynamic.ContainsKey($previous)) {
        return Get-LifetxtDynamicValue $dynamic[$previous] |
            Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { & $result $_ $previous }
    }

    # The command name itself.
    if (-not $command -or $command -eq $wordToComplete) {
        return $LifetxtCommands |
            Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { & $result $_ $LifetxtCommandHelp[$_] }
    }

    # Options, scoped to the command being typed.
    if ($wordToComplete -like '-*') {
        $options = $LifetxtCommandOptions[$command]
        if (-not $options) { $options = @('--config', '--help') }
        return $options |
            Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { & $result $_ $command }
    }

    # A fixed subcommand, or a presence state for the state commands.
    if ($previous -eq $command) {
        if ($LifetxtSubcommands.ContainsKey($command)) {
            return $LifetxtSubcommands[$command] |
                Where-Object { $_ -like "$wordToComplete*" } |
                ForEach-Object { & $result $_ $command }
        }
        if (@('state', 's', 'start') -contains $command) {
            return Get-LifetxtDynamicValue 'state' |
                Where-Object { $_ -like "$wordToComplete*" } |
                ForEach-Object { & $result $_ 'state' }
        }
    }
}
""" % {
        "commands": command_list,
        "help_map": help_map,
        "option_map": option_map,
        "value_map": value_map,
        "subcommand_map": subcommand_map,
    }


def command_completion(args):
    if args.mode == "powershell":
        text = _powershell_completion_script()
        return _emit(text, args.output)
    shell = args.shell
    if shell != "powershell":
        raise ValueError("This extension handles only PowerShell completion installation.")
    text = "Generate and source the completion script in your PowerShell profile:\n\n  lifetxt completion powershell -o $HOME\\Documents\\PowerShell\\lifetxt-completion.ps1\n  . $HOME\\Documents\\PowerShell\\lifetxt-completion.ps1\n"
    return _emit(text, args.output)


def command_quick_journal(args, config_data):
    day = _parse_date(args.date, "journal date") if args.date else timezone_today()
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8-sig") as handle:
            body = handle.read().strip()
    else:
        editor = _resolve_editor(args, config_data)
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False)
        temp_path = handle.name
        try:
            handle.write("# %s\n\n" % (args.title or "Journal %s" % day.isoformat()))
            handle.close()
            return_code = subprocess.call(shlex.split(editor, posix=os.name != "nt") + [temp_path])
            if return_code:
                return return_code
            with open(temp_path, "r", encoding="utf-8-sig") as reader:
                body = reader.read().strip()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    if not body:
        raise ValueError("Journal body is empty; nothing was written.")
    output = args.append or config_write_file(config_data) or "life.txt"
    legacy_args = ["quick", args.title or "Journal %s" % day.isoformat(), "--append", output, "--type", "J", "--status", "[N]", "--on", day.isoformat(), "--body", body, "--no-shorthand"]
    if args.mood:
        legacy_args.extend(("--mood", args.mood))
    if args.project:
        legacy_args.extend(("--project", args.project))
    for tag in args.tags or []:
        legacy_args.extend(("--tag", tag))
    if args.dry_run:
        details = OrderedDict((("on", [day.isoformat()]), ("body", [body])))
        if args.mood:
            details["mood"] = [args.mood]
        if args.project:
            details["project"] = [args.project]
        if args.tags:
            details["tag"] = list(args.tags)
        sys.stdout.write(item_to_line(Item("[N]", "J", args.title or "Journal %s" % day.isoformat(), details)) + "\n")
        return 0
    from .cli import main as legacy_main

    return legacy_main(legacy_args)
