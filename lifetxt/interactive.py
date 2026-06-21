import sys

from .model import (
    KNOWN_KEYS,
    RECOMMENDED_KEY_GROUPS,
    RECOMMENDED_KEYS_BY_TYPE,
    RECOMMENDED_KEYS_BY_STATUS,
    STATUS_ALIASES,
    TYPE_ALIASES,
    VALID_STATUSES,
    VALID_TYPES,
)


TYPE_DESCRIPTIONS = (
    ("T", "Task", "A task or to-do item."),
    ("E", "Event", "A calendar event with from:/to: or on:."),
    ("D", "Deadline", "A due date or due datetime."),
    ("R", "Reminder", "A reminder at a date/time or time."),
    ("H", "Habit", "A recurring habit, usually with repeat:."),
    ("N", "Note", "A note or memo. Usually uses status [N]."),
    ("S", "Status", "A chat-style presence/current-state record."),
    ("M", "Message", "A person-to-person message or notification request."),
)

STATUS_DESCRIPTIONS = (
    ("[ ]", "todo", "Not completed."),
    ("[/]", "doing", "In progress."),
    ("[x]", "done", "Completed."),
    ("[-]", "canceled", "Canceled."),
    ("[>]", "deferred", "Deferred or moved."),
    ("[?]", "pending", "Pending or uncertain."),
    ("[N]", "note", "Note status, normally only for type N."),
)

DETAIL_EXAMPLES = (
    "due:2026-06-12",
    "from:2026-06-08T13:00",
    "to:2026-06-08T14:30",
    "at:18:00",
    "repeat:daily",
    'loc:"Meeting Room A"',
    "tag:important",
)

DETAIL_DESCRIPTIONS = {
    "id": ("Item ID.", "id:task_001"),
    "parent": ("Parent item ID.", "parent:task_001"),
    "created": ("Creation date or datetime.", "created:2026-06-06"),
    "updated": ("Last updated date or datetime.", "updated:2026-06-06T16:30"),
    "done": ("Completion date or datetime.", "done:2026-06-05"),
    "due": ("Deadline date or datetime.", "due:2026-06-12"),
    "do": ("Planned execution date or datetime.", "do:2026-06-10"),
    "from": ("Start datetime.", "from:2026-06-08T13:00"),
    "to": ("End datetime.", "to:2026-06-08T14:30"),
    "state": ("Status / presence state such as busy, away, focus, or sleeping.", "state:busy"),
    "person": ("Person or target whose status is recorded.", "person:self"),
    "owner": ("Person accountable for the item.", "owner:alice"),
    "assignee": ("Person assigned to do the work.", "assignee:alice"),
    "attendee": ("Event participant. Repeat for multiple attendees.", "attendee:alice"),
    "sender": ("Message sender.", "sender:self"),
    "recipient": ("Message recipient. Repeat for multiple recipients.", "recipient:alice"),
    "service": ("Source or target service.", "service:teams"),
    "channel": ("Message channel or delivery route.", "channel:teams"),
    "visibility": ("Visibility scope.", "visibility:team"),
    "notify_at": ("Notification date or datetime.", "notify_at:2026-06-06T09:00"),
    "notify_from": ("Notification period start date or datetime.", "notify_from:2026-06-06T09:00"),
    "notify_to": ("Notification period end date or datetime.", "notify_to:2026-06-06T17:00"),
    "ack": ("Notification acknowledgement date or datetime.", "ack:2026-06-06T09:05"),
    "snooze_until": ("Suppress message notification until this date or datetime.", "snooze_until:2026-06-06T09:30"),
    "on": ("All-day date.", "on:2026-06-08"),
    "at": ("Reminder or execution time.", "at:18:00"),
    "repeat": ("Recurrence value.", "repeat:daily"),
    "project": ("Project name.", "project:research"),
    "context": ("Context or situation.", "context:home"),
    "loc": ("Location.", 'loc:"Meeting Room A"'),
    "priority": ("Priority.", "priority:A"),
    "est": ("Estimated duration.", "est:90m"),
    "tag": ("Tag. Repeat the key for multiple tags.", "tag:important"),
    "note": ("Short note.", 'note:"Check later"'),
    "url": ("Related URL.", "url:https://example.com"),
    "reason": ("Reason, often for canceled items.", 'reason:"Schedule changed"'),
    "moved_to": ("New date or item after deferral.", "moved_to:2026-06-10"),
}


class PromptSession(object):
    def __init__(self, enable_completion=True):
        self.enable_completion = enable_completion
        self.history = []
        self._readline = None
        if enable_completion:
            self._readline = _import_readline()

    def read(self, name, default="", candidates=None, help_topic=None, allow_empty=True):
        candidates = candidates or []
        while True:
            prompt = _format_prompt(name, default)
            value = self._read_once(prompt, default, candidates, help_topic)
            value = value.strip()
            if _is_help_request(value):
                print_help(_help_topic_from_request(value, help_topic))
                print_short_rule()
                continue
            if value == "" and default:
                value = default
            if value or allow_empty:
                if value:
                    self.history.append(value)
                return value

    def _read_once(self, prompt, default, candidates, help_topic):
        completer = FieldCompleter(candidates)
        if self.enable_completion and self._readline is not None:
            return self._read_with_readline(prompt, completer)
        if self.enable_completion and _can_use_msvcrt_editor():
            return WindowsLineEditor(self.history, completer).read(prompt)
        return input(prompt)

    def _read_with_readline(self, prompt, completer):
        readline = self._readline
        old_completer = readline.get_completer()
        old_delims = readline.get_completer_delims()
        readline.set_completer(completer.complete)
        readline.set_completer_delims(" \t\n")
        try:
            try:
                readline.parse_and_bind("tab: complete")
            except Exception:
                pass
            value = input(prompt)
            if value:
                try:
                    readline.add_history(value)
                except Exception:
                    pass
            return value
        finally:
            readline.set_completer(old_completer)
            readline.set_completer_delims(old_delims)


class FieldCompleter(object):
    def __init__(self, candidates):
        self.candidates = list(candidates)
        self.matches = []

    def complete(self, text, state):
        if state == 0:
            self.matches = self.matches_for(text)
        if state < len(self.matches):
            return self.matches[state]
        return None

    def matches_for(self, text):
        prefix = text or ""
        return [candidate for candidate in self.candidates if candidate.startswith(prefix)]

    def complete_value(self, value):
        prefix, token = _completion_prefix(value)
        matches = self.matches_for(token)
        if not matches:
            return value, matches
        common = _common_prefix(matches)
        if len(matches) == 1:
            common = matches[0]
        if common and common != token:
            return prefix + common, matches
        return value, matches


class WindowsLineEditor(object):
    def __init__(self, history, completer):
        self.history = history
        self.completer = completer

    def read(self, prompt):
        import msvcrt

        buffer = []
        cursor = 0
        history_index = len(self.history)
        last_render_len = 0
        sys.stdout.write(prompt)
        sys.stdout.flush()

        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buffer)
            if ch in ("\x00", "\xe0"):
                key = msvcrt.getwch()
                if key == "H":
                    if self.history and history_index > 0:
                        history_index -= 1
                        buffer = list(self.history[history_index])
                        cursor = len(buffer)
                elif key == "P":
                    if history_index < len(self.history) - 1:
                        history_index += 1
                        buffer = list(self.history[history_index])
                    else:
                        history_index = len(self.history)
                        buffer = []
                    cursor = len(buffer)
                elif key == "K" and cursor > 0:
                    cursor -= 1
                elif key == "M" and cursor < len(buffer):
                    cursor += 1
                elif key == "G":
                    cursor = 0
                elif key == "O":
                    cursor = len(buffer)
                elif key == "S" and cursor < len(buffer):
                    del buffer[cursor]
                last_render_len = _render_line(prompt, buffer, cursor, last_render_len)
                continue
            if ch == "\t":
                current = "".join(buffer)
                completed, matches = self.completer.complete_value(current)
                if completed != current:
                    buffer = list(completed)
                    cursor = len(buffer)
                elif matches:
                    sys.stdout.write("\n")
                    sys.stdout.write("  " + "  ".join(matches) + "\n")
                last_render_len = _render_line(prompt, buffer, cursor, last_render_len)
                continue
            if ch in ("\b", "\x7f"):
                if cursor > 0:
                    del buffer[cursor - 1]
                    cursor -= 1
                last_render_len = _render_line(prompt, buffer, cursor, last_render_len)
                continue
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch >= " ":
                buffer.insert(cursor, ch)
                cursor += 1
                last_render_len = _render_line(prompt, buffer, cursor, last_render_len)


def type_candidates():
    aliases = sorted(TYPE_ALIASES.keys())
    return list(VALID_TYPES) + aliases + ["?", "help", "?type"]


def status_candidates():
    aliases = sorted(STATUS_ALIASES.keys())
    return list(VALID_STATUSES) + aliases + ["?", "help", "?status"]


def detail_candidates(kind=None):
    keys = _detail_candidate_keys(kind)
    return [key + ":" for key in keys] + ["?", "help", "?detail"] + [
        "?" + key for key in keys
    ] + ["?all"]


def print_help(topic=None):
    topic = topic or "general"
    if topic.startswith("detail:"):
        _print_detail_help(topic.split(":", 1)[1])
        return
    if topic.startswith("key:"):
        _print_key_help(topic)
        return
    if topic == "type":
        _print_type_help()
    elif topic == "status":
        _print_status_help()
    elif topic == "title":
        _print_title_help()
    elif topic == "detail":
        _print_detail_help(None)
    else:
        print("Interactive assist help")
        print("  Enter ? or help at any prompt to show help.")
        print("  Enter ?type, ?status, or ?detail for specific help.")
        print("  Tab completes values when the terminal supports it; Up/Down recall history.")
        print("  Empty input accepts the displayed default.")
        _print_type_help()
        _print_status_help()


def print_detail_help(kind):
    _print_detail_help(kind)


def print_detail_summary(kind):
    print("Details: key:value or key=value. Empty finishes.")
    print("Help: ?detail lists suggested keys; ?all lists known keys; ?due shows key help.")
    if kind in RECOMMENDED_KEYS_BY_TYPE:
        keys = ", ".join(RECOMMENDED_KEYS_BY_TYPE[kind])
        print("Suggested keys for %s: %s" % (kind, keys))


def print_section(title):
    print("")
    print("-" * 56)
    print(title)


def print_short_rule(after_prompt=False):
    if after_prompt and not sys.stdin.isatty():
        sys.stdout.write("\n")
    print("-" * 32)


def _print_type_help():
    print("Type values:")
    for code, name, description in TYPE_DESCRIPTIONS:
        aliases = _aliases_for(TYPE_ALIASES, code)
        print("  %-2s %-9s %s%s" % (code, name + ":", description, _alias_suffix(aliases)))


def _print_status_help():
    print("Status values:")
    for code, name, description in STATUS_DESCRIPTIONS:
        aliases = _aliases_for(STATUS_ALIASES, code)
        print("  %-3s %-9s %s%s" % (code, name + ":", description, _alias_suffix(aliases)))
    print("Suggested detail keys by status:")
    for code, keys in RECOMMENDED_KEYS_BY_STATUS.items():
        print("  %-3s %s" % (code, ", ".join(keys)))


def _print_title_help():
    print("Title: main item text. Use spaces normally; output quotes it when needed.")


def _print_detail_help(kind):
    if kind == "all":
        print("Known detail keys by category:")
        _print_all_key_tables()
        print("Type-specific and status-specific help lists the shorter recommended set.")
        print("Detail format:")
        print("  key:value or key=value")
        return
    if kind in RECOMMENDED_KEYS_BY_TYPE:
        print("Recommended detail keys for type %s:" % kind)
        keys = RECOMMENDED_KEYS_BY_TYPE[kind]
    else:
        print("Recommended detail key groups:")
        _print_grouped_key_tables(RECOMMENDED_KEY_GROUPS)
        print("Use ?all for every known key. Custom keys are preserved.")
        print("Detail format:")
        print("  key:value or key=value")
        return
    _print_key_table(keys)
    print("Use ?all for every known key. Custom keys are preserved.")
    print("Detail format:")
    print("  key:value or key=value")


def _print_key_help(topic):
    parts = topic.split(":", 2)
    key = parts[2] if len(parts) == 3 else ""
    key = key.rstrip(":")
    if not key:
        _print_detail_help(None)
        return
    entry = DETAIL_DESCRIPTIONS.get(key)
    if entry is None:
        print("No built-in help for detail key %r. Custom keys are preserved." % key)
        print("Use key:value or key=value.")
        return
    description, example = entry
    print("%s: %s" % (key, description))
    print("Example: " + example)
    if key == "state":
        print("Recommended values: available, busy, away, offline, dnd, focus, sleeping, commuting, working, studying, meeting, custom")


def _print_key_table(keys):
    print("| Key | Meaning | Example |")
    print("|---|---|---|")
    for key in keys:
        description, example = DETAIL_DESCRIPTIONS.get(
            key,
            ("Custom detail key.", key + ":value"),
        )
        print(
            "| %s | %s | `%s` |"
            % (
                _escape_table_cell(key),
                _escape_table_cell(description),
                _escape_table_cell(example),
            )
        )


def _print_grouped_key_tables(groups):
    for label, keys in groups:
        print("")
        print("%s keys:" % label)
        _print_key_table(keys)


def _print_all_key_tables():
    _print_grouped_key_tables(RECOMMENDED_KEY_GROUPS)
    grouped = set()
    for _label, keys in RECOMMENDED_KEY_GROUPS:
        grouped.update(keys)
    remaining = [key for key in KNOWN_KEYS if key not in grouped]
    if remaining:
        print("")
        print("Type-specific keys:")
        _print_key_table(remaining)


def _detail_candidate_keys(kind=None):
    keys = []
    if kind in RECOMMENDED_KEYS_BY_TYPE:
        keys.extend(RECOMMENDED_KEYS_BY_TYPE[kind])
    elif kind == "all" or kind is None:
        for label, group_keys in RECOMMENDED_KEY_GROUPS:
            for key in group_keys:
                if key not in keys:
                    keys.append(key)
    for key in KNOWN_KEYS:
        if key not in keys and kind == "all":
            keys.append(key)
    return keys


def _escape_table_cell(value):
    return str(value).replace("|", "\\|")


def _aliases_for(mapping, value):
    return [alias for alias, mapped in sorted(mapping.items()) if mapped == value]


def _alias_suffix(aliases):
    if not aliases:
        return ""
    return " aliases: " + ", ".join(aliases[:5])


def _format_prompt(name, default):
    suffix = " (? for help)"
    if default:
        return "%s [default: %s]%s: " % (name, default, suffix)
    return "%s%s: " % (name, suffix)


def _is_help_request(value):
    value = value.strip().lower()
    return value in ("?", "help", "h") or value.startswith("?") or value.startswith("help ")


def _help_topic_from_request(value, fallback):
    value = value.strip().lower()
    if value in ("?", "help", "h"):
        return fallback
    if value.startswith("?"):
        value = value[1:]
    elif value.startswith("help "):
        value = value[5:]
    value = value.strip()
    if value in ("type", "types", "t"):
        return "type"
    if value in ("status", "statuses", "state"):
        if fallback and fallback.startswith("detail:") and value == "state":
            return "key:" + fallback.split(":", 1)[1] + ":" + value.rstrip(":")
        return "status"
    if value in ("detail", "details", "key", "keys"):
        if fallback and fallback.startswith("detail:"):
            return fallback
        return "detail"
    if value in ("all", "known", "known_keys"):
        return "detail:all"
    if fallback and fallback.startswith("detail:"):
        return "key:" + fallback.split(":", 1)[1] + ":" + value.rstrip(":")
    return fallback


def _completion_prefix(value):
    last_space = value.rfind(" ")
    if last_space == -1:
        return "", value
    return value[: last_space + 1], value[last_space + 1 :]


def _common_prefix(values):
    if not values:
        return ""
    prefix = values[0]
    for value in values[1:]:
        while not value.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _render_line(prompt, buffer, cursor, last_render_len):
    value = "".join(buffer)
    text = prompt + value
    clear_len = max(last_render_len, len(text))
    sys.stdout.write("\r" + " " * clear_len + "\r" + text)
    tail = len(value) - cursor
    if tail:
        sys.stdout.write("\b" * tail)
    sys.stdout.flush()
    return len(text)


def _import_readline():
    try:
        import readline

        return readline
    except Exception:
        return None


def _can_use_msvcrt_editor():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    try:
        import msvcrt  # noqa: F401

        return True
    except Exception:
        return False
