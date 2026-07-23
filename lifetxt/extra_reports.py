"""Stand-up and invoice reporting commands."""

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


def _parse_rates(values, default_rate):
    rates = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--rate must use PROJECT=AMOUNT.")
        project, amount = value.split("=", 1)
        try:
            rates[project] = Decimal(amount)
        except InvalidOperation:
            raise ValueError("Invalid rate amount: %s" % amount)
    try:
        default = Decimal(str(default_rate))
    except InvalidOperation:
        raise ValueError("Invalid --default-rate amount: %s" % default_rate)
    return rates, default


def _round_minutes(minutes, increment):
    if not increment:
        return minutes
    return int(math.ceil(float(minutes) / increment) * increment)


def command_invoice(args, config_data):
    items = _load_items(args.paths, config_data)
    today = timezone_today()
    if args.start:
        start = _parse_date(args.start, "from date")
    else:
        start = today.replace(day=1)
    if args.end:
        end = _parse_date(args.end, "to date")
    else:
        end = datetime.date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    if end < start:
        raise ValueError("Invoice end date must not be earlier than start date.")
    rates, default_rate = _parse_rates(args.rates, args.default_rate)
    minutes_by_project = {}
    for item in items:
        item_date = _latest_date(item)
        if item_date is None or not (start <= item_date <= end):
            continue
        project = _first(item, "project", "(no project)")
        if args.project and project != args.project:
            continue
        minutes = sum((parse_elapsed(value) or 0) for value in _values(item, "elapsed"))
        if not minutes:
            continue
        minutes_by_project[project] = minutes_by_project.get(project, 0) + _round_minutes(minutes, args.round_minutes)
    rows = []
    total = Decimal("0")
    for project in sorted(minutes_by_project):
        minutes = minutes_by_project[project]
        hours = Decimal(minutes) / Decimal(60)
        rate = rates.get(project, default_rate)
        amount = (hours * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += amount
        rows.append(
            OrderedDict(
                (
                    ("project", project),
                    ("minutes", minutes),
                    ("hours", str(hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))),
                    ("rate", str(rate)),
                    ("amount", str(amount)),
                )
            )
        )
    data = OrderedDict((("from", start.isoformat()), ("to", end.isoformat()), ("currency", args.currency), ("rows", rows), ("total", str(total.quantize(Decimal("0.01"))))))
    if args.format == "json":
        text = _json_text(data, args.pretty)
    elif args.format == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("project", "minutes", "hours", "rate", "amount", "currency"))
        for row in rows:
            writer.writerow((row["project"], row["minutes"], row["hours"], row["rate"], row["amount"], args.currency))
        writer.writerow(("TOTAL", "", "", "", data["total"], args.currency))
        text = stream.getvalue()
    elif args.format == "markdown":
        lines = ["# Invoice", "", "Period: %s to %s" % (start, end), "", "| Project | Hours | Rate | Amount |", "|---|---:|---:|---:|"]
        lines.extend("| %s | %s | %s %s | %s %s |" % (row["project"], row["hours"], row["rate"], args.currency, row["amount"], args.currency) for row in rows)
        lines.extend(("", "**Total: %s %s**" % (data["total"], args.currency), ""))
        text = "\n".join(lines)
    else:
        table_rows = [(row["project"], row["minutes"], row["hours"], row["rate"], row["amount"]) for row in rows]
        text = "Invoice %s to %s (%s)\n" % (start, end, args.currency) + _table(("PROJECT", "MIN", "HOURS", "RATE", "AMOUNT"), table_rows) + "TOTAL: %s %s\n" % (data["total"], args.currency)
    return _emit(text, args.output)


def _assigned_to(item, user, include_unassigned=False):
    people = []
    for key in ("assignee", "owner", "user", "person"):
        people.extend(_values(item, key))
    return user in people or (include_unassigned and not people)


def command_standup(args, config_data):
    items = _load_items(args.paths, config_data)
    day = _parse_date(args.date, "standup date") if args.date else timezone_today()
    yesterday = day - datetime.timedelta(days=1)
    user = args.user or config_user_name(config_data)
    id_map = dict((_item_id(item), item) for item in items if _item_id(item))
    done = []
    planned = []
    blocked = []
    for item in items:
        if item.kind != "T" or not _assigned_to(item, user, args.include_unassigned):
            continue
        done_dates = [_date_value(value) for value in _values(item, "done")]
        if item.status == "[x]" and yesterday in done_dates:
            done.append(item)
        if item.status in OPEN_STATUSES:
            due_or_do = [_date_value(value) for key in ("do", "due") for value in _values(item, key)]
            if item.status == "[/]" or day in due_or_do:
                planned.append(item)
            if _blocked(item, id_map):
                blocked.append(item)
    data = OrderedDict(
        (
            ("date", day.isoformat()),
            ("user", user),
            ("done_yesterday", [_item_record(item) for item in done]),
            ("planned_today", [_item_record(item) for item in planned]),
            ("blocked", [_item_record(item) for item in blocked]),
        )
    )
    if args.format == "json":
        text = _json_text(data, args.pretty)
    else:
        def lines_for(values):
            return ["- %s%s" % (item.title, " (`%s`)" % _item_id(item) if _item_id(item) else "") for item in values] or ["- None"]
        if args.format == "slack":
            sections = ["*Standup — %s — %s*" % (day, user), "*Done yesterday*", *lines_for(done), "*Planned today*", *lines_for(planned), "*Blocked*", *lines_for(blocked)]
        elif args.format == "markdown":
            sections = ["# Standup — %s — %s" % (day, user), "", "## Done yesterday", *lines_for(done), "", "## Planned today", *lines_for(planned), "", "## Blocked", *lines_for(blocked)]
        else:
            sections = ["Standup — %s — %s" % (day, user), "", "Done yesterday:", *lines_for(done), "", "Planned today:", *lines_for(planned), "", "Blocked:", *lines_for(blocked)]
        text = "\n".join(sections) + "\n"
    return _emit(text, args.output)
