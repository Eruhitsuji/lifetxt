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

from .atomic import atomic_write_text
from .config import config_paths, config_section, config_user_name, config_write_file, load_config
from .model import Item
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_to_line
from .timeutil import parse_elapsed

from .extra_common import *


_MARKDOWN_TASK_RE = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.*)$")


def _ics_escape(value):
    return str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _ics_fold(line):
    chunks = []
    current = ""
    current_bytes = 0
    limit = 75
    for char in line:
        size = len(char.encode("utf-8"))
        if current and current_bytes + size > limit:
            chunks.append(current)
            current = " " + char
            current_bytes = 1 + size
            limit = 74
        else:
            current += char
            current_bytes += size
    chunks.append(current)
    return "\r\n".join(chunks)


def _ics_datetime(value):
    text = str(value)
    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+0000"
    elif len(normalized) >= 6 and normalized[-6] in ("+", "-") and normalized[-3] == ":":
        normalized = normalized[:-3] + normalized[-2:]
    formats = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    )
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(normalized, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError("Invalid event datetime for ICS export: %s" % value)
    if parsed.tzinfo is not None:
        return parsed.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return parsed.strftime("%Y%m%dT%H%M%S")


def command_to_ics(args, config_data):
    items = _load_items(args.paths, config_data)
    now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//lifetxt//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:%s" % _ics_escape(args.calendar_name)]
    for item in items:
        if item.kind != "E" or item.status in ("[-]", "[>]"):
            continue
        on = _first(item, "on")
        start = _first(item, "from")
        end = _first(item, "to")
        if not on and not start:
            continue
        uid = _first(item, "uid") or _item_id(item) or hashlib.sha256((item.title + str(item.source) + str(item.line)).encode("utf-8")).hexdigest()[:20] + "@lifetxt"
        lines.extend(("BEGIN:VEVENT", "UID:%s" % _ics_escape(uid), "DTSTAMP:%s" % now, "SUMMARY:%s" % _ics_escape(item.title)))
        if on:
            on_date = _parse_date(on, "event on date")
            lines.append("DTSTART;VALUE=DATE:%s" % on_date.strftime("%Y%m%d"))
            lines.append("DTEND;VALUE=DATE:%s" % (on_date + datetime.timedelta(days=1)).strftime("%Y%m%d"))
        else:
            lines.append("DTSTART:%s" % _ics_datetime(start))
            if end:
                lines.append("DTEND:%s" % _ics_datetime(end))
        if _first(item, "loc"):
            lines.append("LOCATION:%s" % _ics_escape(_first(item, "loc")))
        description = "\n".join(_values(item, "body") + _values(item, "note"))
        if description:
            lines.append("DESCRIPTION:%s" % _ics_escape(description))
        for attendee in _values(item, "attendee"):
            if "@" in attendee and " " not in attendee:
                lines.append("ATTENDEE:mailto:%s" % _ics_escape(attendee))
            else:
                lines.append("X-LIFETXT-ATTENDEE:%s" % _ics_escape(attendee))
        repeat = _first(item, "repeat")
        if repeat.upper().startswith("RRULE:"):
            lines.append(repeat)
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    text = "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"
    return _emit(text, args.output)


def _stable_id(prefix, seed):
    return prefix + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _todo_item(raw, source, line_no, project_override=None, tags=None):
    text = raw.strip()
    if not text:
        return None
    completed = text.startswith("x ")
    if completed:
        text = text[2:].lstrip()
    details = OrderedDict()
    date_tokens = []
    while re.match(r"^\d{4}-\d{2}-\d{2}(?:\s|$)", text):
        token, _, text = text.partition(" ")
        date_tokens.append(token)
        text = text.lstrip()
    priority_match = re.match(r"^\(([A-Z])\)\s+", text)
    if priority_match:
        details["priority"] = [priority_match.group(1)]
        text = text[priority_match.end() :]
    projects = re.findall(r"(?<!\S)\+([A-Za-z0-9_.-]+)", text)
    contexts = re.findall(r"(?<!\S)@([A-Za-z0-9_.-]+)", text)
    text = re.sub(r"(?<!\S)[+@][A-Za-z0-9_.-]+", "", text)
    text = " ".join(text.split())
    if project_override:
        projects.insert(0, project_override)
    if projects:
        details["project"] = list(OrderedDict.fromkeys(projects))
    if contexts:
        details["context"] = list(OrderedDict.fromkeys(contexts))
    if tags:
        details["tag"] = list(tags)
    if completed and date_tokens:
        details["done"] = [date_tokens[0]]
        if len(date_tokens) > 1:
            details["created"] = [date_tokens[1]]
    elif date_tokens:
        details["created"] = [date_tokens[0]]
    details["source"] = ["todo.txt"]
    details["id"] = [_stable_id("todo_", "%s:%s:%s" % (source, line_no, raw))]
    return Item("[x]" if completed else "[ ]", "T", text or "Untitled", details, line=line_no)


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
        for line_no, raw in enumerate(text.splitlines(), 1):
            item = _todo_item(raw, source, line_no, args.project, args.tags)
            if item is not None:
                items.append(item)
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
                details["done"] = [datetime.date.today().isoformat()]
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                details["parent"] = [stack[-1][1]]
            item = Item("[x]" if done else "[ ]", "T", cleaned, details, line=line_no, indent=indent)
            items.append(item)
            stack.append((indent, item_id))
    output = "".join(item_to_line(item) + "\n" for item in items)
    _write_output(output, args.output, args.append)
    return 0
