from collections import OrderedDict


VALID_STATUSES = ("[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]")
VALID_TYPES = ("T", "E", "D", "R", "H", "N", "S", "M")

STATUS_ALIASES = {
    "todo": "[ ]",
    "open": "[ ]",
    "not_completed": "[ ]",
    "queued": "[ ]",
    "scheduled": "[ ]",
    "progress": "[/]",
    "in_progress": "[/]",
    "doing": "[/]",
    "active": "[/]",
    "sending": "[/]",
    "done": "[x]",
    "complete": "[x]",
    "completed": "[x]",
    "sent": "[x]",
    "delivered": "[x]",
    "cancel": "[-]",
    "canceled": "[-]",
    "cancelled": "[-]",
    "defer": "[>]",
    "deferred": "[>]",
    "moved": "[>]",
    "pending": "[?]",
    "unknown": "[?]",
    "n": "[N]",
    "note": "[N]",
    "x": "[x]",
    "/": "[/]",
    "-": "[-]",
    ">": "[>]",
    "?": "[?]",
}

TYPE_ALIASES = {
    "task": "T",
    "todo": "T",
    "event": "E",
    "calendar": "E",
    "deadline": "D",
    "due": "D",
    "reminder": "R",
    "remind": "R",
    "habit": "H",
    "recurring": "H",
    "note": "N",
    "memo": "N",
    "presence": "S",
    "presence_status": "S",
    "status": "S",
    "state": "S",
    "message": "M",
    "msg": "M",
    "mail": "M",
    "notification": "M",
}

KNOWN_KEYS = (
    "id",
    "parent",
    "created",
    "updated",
    "done",
    "due",
    "do",
    "from",
    "to",
    "state",
    "user",
    "person",
    "owner",
    "assignee",
    "attendee",
    "sender",
    "recipient",
    "team",
    "group",
    "service",
    "channel",
    "visibility",
    "notify_at",
    "notify_from",
    "notify_to",
    "ack",
    "snooze_until",
    "on",
    "at",
    "repeat",
    "project",
    "context",
    "loc",
    "priority",
    "est",
    "tag",
    "note",
    "url",
    "reason",
    "moved_to",
)

COMMON_RECOMMENDED_KEYS = ("id", "parent", "project", "tag", "note", "url")
PEOPLE_RECOMMENDED_KEYS = (
    "user",
    "person",
    "owner",
    "assignee",
    "attendee",
    "sender",
    "recipient",
)
TEAM_RECOMMENDED_KEYS = ("team", "group")
TIME_RECOMMENDED_KEYS = ("from", "to", "on", "at", "due", "do", "done")
MESSAGE_RECOMMENDED_KEYS = (
    "sender",
    "recipient",
    "notify_at",
    "notify_from",
    "notify_to",
    "ack",
    "snooze_until",
    "channel",
)
WORKFLOW_RECOMMENDED_KEYS = ("reason", "moved_to")
SYSTEM_RECOMMENDED_KEYS = ("created", "updated")

RECOMMENDED_KEY_GROUPS = (
    ("Common", COMMON_RECOMMENDED_KEYS),
    ("People", PEOPLE_RECOMMENDED_KEYS),
    ("Teams", TEAM_RECOMMENDED_KEYS),
    ("Time", TIME_RECOMMENDED_KEYS),
    ("Message", MESSAGE_RECOMMENDED_KEYS),
    ("Workflow", WORKFLOW_RECOMMENDED_KEYS),
    ("System", SYSTEM_RECOMMENDED_KEYS),
)

# Backward-compatible alias for callers that expect the full known-key list.
RECOMMENDED_KEYS = KNOWN_KEYS

RECOMMENDED_KEYS_BY_TYPE = {
    "T": (
        "do",
        "due",
        "priority",
        "assignee",
        "owner",
        "team",
        "est",
        "project",
        "tag",
        "note",
        "id",
        "parent",
    ),
    "E": (
        "from",
        "to",
        "on",
        "loc",
        "attendee",
        "owner",
        "team",
        "project",
        "tag",
        "note",
    ),
    "D": (
        "due",
        "priority",
        "owner",
        "assignee",
        "team",
        "project",
        "tag",
        "note",
    ),
    "R": (
        "at",
        "on",
        "owner",
        "team",
        "project",
        "context",
        "note",
    ),
    "H": (
        "repeat",
        "at",
        "on",
        "owner",
        "team",
        "project",
        "tag",
        "note",
    ),
    "N": (
        "project",
        "context",
        "tag",
        "note",
        "url",
        "id",
        "parent",
    ),
    "S": (
        "from",
        "state",
        "to",
        "person",
        "team",
        "group",
        "service",
        "loc",
        "project",
        "note",
        "visibility",
    ),
    "M": (
        "sender",
        "recipient",
        "team",
        "group",
        "notify_at",
        "notify_from",
        "notify_to",
        "ack",
        "snooze_until",
        "channel",
        "service",
        "priority",
        "project",
        "tag",
        "note",
        "url",
        "id",
        "parent",
        "created",
        "updated",
    ),
}

RECOMMENDED_KEYS_BY_STATUS = {
    "[ ]": ("do", "due", "priority", "project", "tag", "note"),
    "[/]": ("do", "due", "project", "context", "note", "updated"),
    "[x]": ("done", "project", "tag", "note"),
    "[-]": ("reason", "updated", "note"),
    "[>]": ("moved_to", "reason", "updated", "note"),
    "[?]": ("note", "updated"),
    "[N]": ("project", "context", "tag", "note", "url"),
}

DATE_KEYS = ("on",)
TIME_KEYS = ()
DATETIME_KEYS = ("from", "to")
DATE_OR_DATETIME_KEYS = (
    "created",
    "updated",
    "done",
    "due",
    "do",
    "moved_to",
    "notify_at",
    "notify_from",
    "notify_to",
    "ack",
    "snooze_until",
)
TIME_OR_DATETIME_KEYS = ("at",)
SIMPLE_REPEAT_VALUES = ("daily", "weekly", "monthly", "yearly")
STATUS_STATE_VALUES = (
    "available",
    "busy",
    "away",
    "offline",
    "dnd",
    "focus",
    "sleeping",
    "commuting",
    "working",
    "studying",
    "meeting",
    "custom",
)


class Diagnostic(object):
    """A parser or validator message."""

    def __init__(self, severity, code, message, line=None, column=None, source=None):
        self.severity = severity
        self.code = code
        self.message = message
        self.line = line
        self.column = column
        self.source = source

    def to_dict(self):
        data = OrderedDict()
        data["severity"] = self.severity
        data["code"] = self.code
        data["message"] = self.message
        if self.source is not None:
            data["source"] = self.source
        if self.line is not None:
            data["line"] = self.line
        if self.column is not None:
            data["column"] = self.column
        return data

    def format(self):
        location = ""
        if self.source is not None and self.line is not None and self.column is not None:
            location = "%s:%s:%s: " % (self.source, self.line, self.column)
        elif self.source is not None and self.line is not None:
            location = "%s:%s: " % (self.source, self.line)
        elif self.source is not None:
            location = "%s: " % self.source
        elif self.line is not None and self.column is not None:
            location = "%s:%s: " % (self.line, self.column)
        elif self.line is not None:
            location = "%s: " % self.line
        return "%s%s %s: %s" % (
            location,
            self.severity.upper(),
            self.code,
            self.message,
        )


class Item(object):
    """A parsed life.txt item."""

    def __init__(self, status, kind, title, details=None, line=None, source_text=None, source=None):
        self.status = status
        self.kind = kind
        self.title = title
        self.details = OrderedDict()
        self.line = line
        self.source_text = source_text
        self.source = source
        if details:
            for key, values in details.items():
                if isinstance(values, list):
                    self.details[key] = list(values)
                elif isinstance(values, tuple):
                    self.details[key] = list(values)
                else:
                    self.details[key] = [values]

    def to_dict(self):
        data = OrderedDict()
        data["status"] = self.status
        data["type"] = self.kind
        data["title"] = self.title
        details = OrderedDict()
        for key, values in self.details.items():
            details[key] = list(values)
        data["details"] = details
        return data


def normalize_status(value):
    if value is None:
        return None
    if value in VALID_STATUSES:
        return value
    key = str(value).strip().lower().replace("-", "_")
    return STATUS_ALIASES.get(key, value)


def normalize_type(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in VALID_TYPES:
        return value
    return TYPE_ALIASES.get(value.lower().replace("-", "_"), value)
