from collections import OrderedDict


VALID_STATUSES = ("[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]")
VALID_TYPES = ("T", "E", "D", "R", "H", "N", "S")

STATUS_ALIASES = {
    "todo": "[ ]",
    "open": "[ ]",
    "not_completed": "[ ]",
    "progress": "[/]",
    "in_progress": "[/]",
    "doing": "[/]",
    "done": "[x]",
    "complete": "[x]",
    "completed": "[x]",
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
}

RECOMMENDED_KEYS = (
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
    "person",
    "service",
    "visibility",
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

RECOMMENDED_KEYS_BY_TYPE = {
    "T": (
        "do",
        "due",
        "project",
        "context",
        "priority",
        "est",
        "tag",
        "note",
        "url",
        "id",
        "parent",
        "created",
        "updated",
        "done",
    ),
    "E": (
        "from",
        "to",
        "on",
        "loc",
        "project",
        "tag",
        "note",
        "url",
        "id",
        "created",
        "updated",
    ),
    "D": (
        "due",
        "project",
        "priority",
        "tag",
        "note",
        "url",
        "id",
        "created",
        "updated",
        "done",
    ),
    "R": (
        "at",
        "on",
        "project",
        "context",
        "priority",
        "tag",
        "note",
        "url",
        "id",
        "created",
        "updated",
        "done",
    ),
    "H": (
        "repeat",
        "at",
        "on",
        "project",
        "context",
        "priority",
        "tag",
        "note",
        "id",
        "created",
        "updated",
        "done",
    ),
    "N": (
        "project",
        "context",
        "tag",
        "note",
        "url",
        "id",
        "parent",
        "created",
        "updated",
    ),
    "S": (
        "from",
        "state",
        "to",
        "person",
        "service",
        "loc",
        "project",
        "note",
        "visibility",
    ),
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

    def __init__(self, severity, code, message, line=None, column=None):
        self.severity = severity
        self.code = code
        self.message = message
        self.line = line
        self.column = column

    def to_dict(self):
        data = OrderedDict()
        data["severity"] = self.severity
        data["code"] = self.code
        data["message"] = self.message
        if self.line is not None:
            data["line"] = self.line
        if self.column is not None:
            data["column"] = self.column
        return data

    def format(self):
        location = ""
        if self.line is not None and self.column is not None:
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

    def __init__(self, status, kind, title, details=None, line=None):
        self.status = status
        self.kind = kind
        self.title = title
        self.details = OrderedDict()
        self.line = line
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
