"""iCalendar, todo.txt, and GitHub Markdown conversion commands."""

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

from .timezone_policy import today as timezone_today

from .atomic import atomic_write_text
from .config import (
    config_paths,
    config_section,
    config_user_name,
    config_write_file,
    load_config,
)
from .model import Item
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_to_line
from .timeutil import parse_elapsed
from .conversion import encode_items as encode_conversion_items, items_from_todo_text

from .extra_common import *


_MARKDOWN_TASK_RE = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.*)$")


def command_to_ics(args, config_data):
    items = _load_items(args.paths, config_data)
    text = encode_conversion_items(
        items,
        "ics",
        calendar_name=args.calendar_name,
        reject_loss=False,
    )
    return _emit(text, args.output)


def _stable_id(prefix, seed):
    return prefix + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def command_from_todo(args, config_data):
    paths = expand_paths(args.paths or ["-"])
    items = []
    for path in paths:
        if path == "-":
            text = sys.stdin.read()
            source = "stdin"
        else:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
            source = os.path.abspath(path)
        items.extend(
            items_from_todo_text(
                text, source=source, project=args.project, tags=args.tags
            )
        )
    output = "".join(item_to_line(item) + "\n" for item in items)
    _write_output(output, args.output, args.append)
    return 0


def command_from_markdown(args, config_data):
    if args.preset != "github":
        raise ValueError("from-markdown currently supports --preset github.")
    paths = expand_paths(args.paths or ["-"])
    items = []
    for path in paths:
        if path == "-":
            text = sys.stdin.read()
            source = "stdin"
        else:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
            source = os.path.abspath(path)
        stack = []
        for line_no, raw in enumerate(text.splitlines(), 1):
            match = _MARKDODN_TASK_RE.match(raw)
            if not match:
                continue
            indent = len(match.group(1).replace("\t", "    "))
            done = match.group(2).lower() == "x"
            title = match.group(3)
            assignees = re.findall(r"(?<![\w@])@([A-Za-z0-9-]+)", title)
            refs = re.findall(r"(?<!\w)#(\d+)\b", title)
            cleaned = re.sub(r"(?<![\w@])@[A-Za-z0-9-]+", "", title)
            cleaned = re.sub(r"(?<!\w)#\d+\b", "", cleaned)
            cleaned = "_".join(cleaned.split()) or "Untitled"
            item_id = _stable_id("md_", "%s:%s:%s" % (source, line_no, raw))
            details = OrderedDict((("id", [item_id]), ("source", ["markdown"])))
            if args.project:
                details["project"] = [args.project]
            if args.tags:
                details["tag"] = list(args.tags)
            if assignees:
                details["assignee"] = list(OrderedDict.fromkeys(assignees))
            if refs:
                details["ref"] = ["github#%s" % value for value in refs]
            if done:
                details["done"] = [timezone_today().isoformat()]
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                details["parent"] = [stack[-1][1]]
            item = Item(
                "[x]" if done else "[ ]",
                "T",
                cleaned,
                details,
                line=line_no,
                indent=indent,
            )
            items.append(item)
            stack.append((indent, item_id))
    output = "".join(item_to_line(item) + "\n" for item in items)
    _write_output(output, args.output, args.append)
    return 0
