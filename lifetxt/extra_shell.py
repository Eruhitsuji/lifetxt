"""Shell completion and journal capture commands."""

import argparse
import calendar
import csv
import datetime
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
    commands = sorted(
        set(
            (
                "agenda", "archive", "assist", "batch", "check", "cleanup", "complete", "completion", "config", "count", "demo", "deps", "doctor", "done", "edit", "files", "filter", "from-csv", "from-json", "from-jsonl", "from-markdown", "from-todo", "fzf", "git-hook", "health", "ids", "import-ics", "inbox", "invoice", "links", "markdown", "mcp", "next", "notify", "path", "quick", "review", "search", "serve", "show", "standup", "start", "state", "stats", "status", "stop", "summary", "sync-ics", "timer", "to-csv", "to-ics", "to-json", "to-jsonl", "tui", "undo", "who"
            )
        )
    )
    quoted = ", ".join("'%s'" % value for value in commands)
    return """# lifetxt PowerShell native argument completion\n$LifetxtCommands = @(%s)\nRegister-ArgumentCompleter -Native -CommandName lifetxt -ScriptBlock {\n    param($wordToComplete, $commandAst, $cursorPosition)\n    $tokens = $commandAst.CommandElements\n    if ($tokens.Count -le 2) {\n        $LifetxtCommands | Where-Object { $_ -like \"$wordToComplete*\" } | ForEach-Object {\n            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)\n        }\n    }\n}\n""" % quoted


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
    day = _parse_date(args.date, "journal date") if args.date else datetime.date.today()
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
