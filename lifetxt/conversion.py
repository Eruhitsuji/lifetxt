"""Surface-neutral text conversion through the shared :class:`Item` model.

The registry in this module is the authoritative conversion capability source
for the CLI and future stateless adapters.  It deliberately owns no file,
network, workspace, or synchronization behavior.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re

from .csvio import items_from_csv_text, items_to_csv
from .ics import items_from_ics_text, items_to_ics_text
from .model import Item
from .native_codec import items_to_life_text
from .parser import parse_text
from .serializer import (
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)
from .validator import validate_item


CAPABILITY_SCHEMA = "lifetxt-conversion-capabilities-v1"
CANONICAL_FORMATS = (
    "life",
    "json",
    "jsonl",
    "csv",
    "ics",
    "markdown-task-list",
    "todo",
)
SOURCE_FORMATS = CANONICAL_FORMATS
TARGET_FORMATS = ("life", "json", "jsonl", "csv", "ics", "todo")

# The four item-preserving text targets are safe for every decoder. ICS is
# intentionally narrower; todo is task-oriented and only supports life input.
SUPPORTED_PAIRS = tuple(
    (source, target)
    for source in SOURCE_FORMATS
    for target in ("life", "json", "jsonl", "csv")
) + (("life", "ics"), ("life", "todo"))


class ConversionError(ValueError):
    """Base error for deterministic conversion contract failures."""


class UnknownFormatError(ConversionError):
    """A source or target name is outside the canonical vocabulary."""


class UnsupportedConversionError(ConversionError):
    """Both formats exist, but their pair is not in the capability matrix."""


class InvalidConversionInputError(ConversionError):
    """Source content cannot produce valid shared items."""


class ConversionLossError(ConversionError):
    """The requested encoder would silently discard shared-item semantics."""


@dataclass(frozen=True)
class ConversionResult:
    content: str
    item_count: int
    diagnostics: tuple


def conversion_capabilities():
    """Return the stable, JSON-serializable conversion capability matrix."""
    return OrderedDict(
        (
            ("schema", CAPABILITY_SCHEMA),
            ("formats", list(CANONICAL_FORMATS)),
            ("source_formats", list(SOURCE_FORMATS)),
            ("target_formats", list(TARGET_FORMATS)),
            (
                "pairs",
                [
                    OrderedDict((("from", source), ("to", target)))
                    for source, target in SUPPORTED_PAIRS
                ],
            ),
        )
    )


def _diagnostic_errors(diagnostics):
    return [entry for entry in diagnostics if entry.severity == "error"]


def _invalid_message(diagnostics):
    errors = _diagnostic_errors(diagnostics)
    if not errors:
        return "Conversion input is invalid."
    return "Invalid conversion input: " + "; ".join(
        "%s %s" % (entry.code, entry.message) for entry in errors
    )


def _validate_decoded_items(items, diagnostics=()):
    combined = list(diagnostics)
    for item in items:
        combined.extend(validate_item(item))
    if _diagnostic_errors(combined):
        raise InvalidConversionInputError(_invalid_message(combined))
    return items, tuple(combined)


def decode_text(
    source_format,
    content,
    *,
    source_name="content",
    project=None,
    tags=None,
    kind="T",
    id_key="id",
    validate=True,
):
    """Decode one textual payload to shared items and non-error diagnostics."""
    if source_format not in SOURCE_FORMATS:
        raise UnknownFormatError(
            "Unknown source format %r. Known source formats: %s."
            % (source_format, ", ".join(SOURCE_FORMATS))
        )
    try:
        if source_format == "life":
            items, diagnostics = parse_text(
                content,
                id_key=id_key,
                check_ids=False,
                check_references=False,
            )
            if validate and _diagnostic_errors(diagnostics):
                raise InvalidConversionInputError(_invalid_message(diagnostics))
            return items, tuple(diagnostics)
        if source_format == "json":
            items = items_from_json_text(content)
        elif source_format == "jsonl":
            items = items_from_jsonl_text(content)
        elif source_format == "csv":
            items = items_from_csv_text(content)
        elif source_format == "ics":
            items = items_from_ics_text(content, project=project, tags=tags)
        elif source_format == "markdown-task-list":
            items = items_from_markdown_task_list_text(
                content, project=project, kind=kind, tags=tags
            )
        else:
            items = items_from_todo_text(
                content, source=source_name, project=project, tags=tags
            )
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        if isinstance(exc, ConversionError):
            raise
        raise InvalidConversionInputError(
            "Invalid %s conversion input: %s" % (source_format, exc)
        ) from exc
    if validate:
        return _validate_decoded_items(items)
    return items, ()


def _assert_lossless_ics_items(items):
    rejected = []
    for index, item in enumerate(items, 1):
        if (
            item.kind != "E"
            or item.status in ("[-]", "[>]")
            or not (item.details.get("on") or item.details.get("from"))
        ):
            rejected.append(str(index))
    if rejected:
        raise ConversionLossError(
            "Cannot convert to ics without dropping item(s) %s. ICS output "
            "requires active Event items with on: or from:." % ", ".join(rejected)
        )


_TODO_TAG_KEY_RE = re.compile(r"^[^\s:]+$")
_TODO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TODO_PRIORITY_RE = re.compile(r"^\(([A-Z])\)$")
_TODO_KV_RE = re.compile(r"^([^\s:]+):([^\s:]+)$")


def _todo_date_value(value, *, item_no, key):
    if not isinstance(value, str) or not _TODO_DATE_RE.fullmatch(value):
        raise ConversionLossError(
            "Cannot convert item %s field %s to todo: expected YYYY-MM-DD."
            % (item_no, key)
        )
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ConversionLossError(
            "Cannot convert item %s field %s to todo: invalid calendar date %r."
            % (item_no, key, value)
        ) from exc
    return value


def _todo_values(item, key, item_no):
    values = item.details.get(key, [])
    if not isinstance(values, list):
        raise ConversionLossError(
            "Cannot convert item %s field %s to todo: details must be arrays."
            % (item_no, key)
        )
    return values


def _todo_title_tokens(title, item_no, status):
    if not isinstance(title, str) or not title or title != title.strip():
        raise ConversionLossError(
            "Cannot convert item %s field title to todo: title must be non-empty "
            "with no leading or trailing whitespace." % item_no
        )
    if any(char.isspace() and char not in " \t" for char in title):
        raise ConversionLossError(
            "Cannot convert item %s field title to todo: line breaks are unsupported."
            % item_no
        )
    if "  " in title or "\t" in title:
        raise ConversionLossError(
            "Cannot convert item %s field title to todo: todo decoding normalizes "
            "repeated whitespace." % item_no
        )
    tokens = title.split(" ")
    if status == "[ ]" and tokens[0] == "x":
        raise ConversionLossError(
            "Cannot convert item %s field title to todo: a leading 'x ' would "
            "mark the task complete." % item_no
        )
    if _TODO_PRIORITY_RE.fullmatch(tokens[0]) or _TODO_DATE_RE.fullmatch(tokens[0]):
        raise ConversionLossError(
            "Cannot convert item %s field title to todo: its leading token would "
            "be read as priority or date." % item_no
        )
    for token in tokens:
        if (token.startswith("+") or token.startswith("@")) and len(token) > 1:
            raise ConversionLossError(
                "Cannot convert item %s field title to todo: token %r would be "
                "read as a project or context." % (item_no, token)
            )
        if _TODO_KV_RE.fullmatch(token):
            raise ConversionLossError(
                "Cannot convert item %s field title to todo: token %r would be "
                "read as metadata." % (item_no, token)
            )
    return tokens


def _items_to_todo_text(items):
    lines = []
    for item_no, item in enumerate(items, 1):
        if item.kind != "T":
            raise ConversionLossError(
                "Cannot convert item %s field type=%s to todo: only Task (T) "
                "items are representable." % (item_no, item.kind)
            )
        if item.status not in ("[ ]", "[x]"):
            raise ConversionLossError(
                "Cannot convert item %s field status=%s to todo: only [ ] and [x] "
                "are representable." % (item_no, item.status)
            )
        title_tokens = _todo_title_tokens(item.title, item_no, item.status)
        parts = []
        if item.status == "[x]":
            parts.append("x")
            done = _todo_values(item, "done", item_no)
            created = _todo_values(item, "created", item_no)
            if len(done) > 1 or len(created) > 1:
                raise ConversionLossError(
                    "Cannot convert item %s fields done/created to todo: at most "
                    "one date for each field is representable." % item_no
                )
            if created and not done:
                raise ConversionLossError(
                    "Cannot convert item %s field created to todo: a completed task "
                    "needs done: before created: to preserve date meaning." % item_no
                )
            if done:
                parts.append(_todo_date_value(done[0], item_no=item_no, key="done"))
            if created:
                parts.append(
                    _todo_date_value(created[0], item_no=item_no, key="created")
                )
        else:
            done = _todo_values(item, "done", item_no)
            if done:
                raise ConversionLossError(
                    "Cannot convert item %s field done to todo: a completion "
                    "date requires completed status [x]." % item_no
                )
            priority = _todo_values(item, "priority", item_no)
            if len(priority) > 1 or (
                priority
                and (
                    not isinstance(priority[0], str)
                    or not re.fullmatch(r"[A-Z]", priority[0])
                )
            ):
                raise ConversionLossError(
                    "Cannot convert item %s field priority to todo: expected one "
                    "uppercase letter A-Z." % item_no
                )
            created = _todo_values(item, "created", item_no)
            if len(created) > 1:
                raise ConversionLossError(
                    "Cannot convert item %s field created to todo: at most one "
                    "date is representable." % item_no
                )
            if priority:
                parts.append("(%s)" % priority[0])
            if created:
                parts.append(
                    _todo_date_value(created[0], item_no=item_no, key="created")
                )
        parts.extend(title_tokens)

        for key in ("project", "context"):
            for value in _todo_values(item, key, item_no):
                if (
                    not isinstance(value, str)
                    or not value
                    or any(c.isspace() for c in value)
                ):
                    raise ConversionLossError(
                        "Cannot convert item %s field %s to todo: each value must "
                        "be one non-empty token." % (item_no, key)
                    )
                parts.append(("+" if key == "project" else "@") + value)

        if item.status == "[x]":
            priority = _todo_values(item, "priority", item_no)
            if len(priority) > 1 or (
                priority
                and (
                    not isinstance(priority[0], str)
                    or not re.fullmatch(r"[A-Z]", priority[0])
                )
            ):
                raise ConversionLossError(
                    "Cannot convert item %s field priority to todo: expected one "
                    "uppercase letter A-Z." % item_no
                )
            if priority:
                parts.append("pri:%s" % priority[0])

        for key, values in item.details.items():
            if key in ("project", "context", "priority", "created", "done"):
                continue
            if not isinstance(key, str) or not _TODO_TAG_KEY_RE.fullmatch(key):
                raise ConversionLossError(
                    "Cannot convert item %s field %r to todo: metadata keys must "
                    "be non-empty tokens without colons." % (item_no, key)
                )
            if not isinstance(values, list):
                raise ConversionLossError(
                    "Cannot convert item %s field %s to todo: details must be arrays."
                    % (item_no, key)
                )
            for value in values:
                if (
                    not isinstance(value, str)
                    or not value
                    or any(c.isspace() for c in value)
                    or ":" in value
                ):
                    raise ConversionLossError(
                        "Cannot convert item %s field %s to todo: metadata values "
                        "must be non-empty tokens without colons." % (item_no, key)
                    )
                parts.append("%s:%s" % (key, value))
        lines.append(" ".join(parts))
    return "".join(line + "\n" for line in lines)


def encode_items(
    items,
    target_format,
    *,
    pretty=False,
    canonical=False,
    id_key="id",
    calendar_name="lifetxt",
    generated_at=None,
    reject_loss=True,
):
    """Encode shared items to one canonical textual target format."""
    if target_format not in TARGET_FORMATS:
        if target_format in CANONICAL_FORMATS:
            raise UnsupportedConversionError(
                "Format %r is source-only and cannot be used as a target."
                % target_format
            )
        raise UnknownFormatError(
            "Unknown target format %r. Known target formats: %s."
            % (target_format, ", ".join(TARGET_FORMATS))
        )
    items = list(items)
    if target_format == "life":
        return items_to_life_text(items, canonical=canonical, key=id_key)
    if target_format == "json":
        return items_to_json(items, pretty=pretty) + "\n"
    if target_format == "jsonl":
        output = items_to_jsonl(items)
        return output + "\n" if output else ""
    if target_format == "csv":
        return items_to_csv(items)
    if target_format == "todo":
        return _items_to_todo_text(items)
    if reject_loss:
        _assert_lossless_ics_items(items)
    return items_to_ics_text(
        items, calendar_name=calendar_name, generated_at=generated_at
    )


def convert_text(source_format, target_format, content, **options):
    """Convert one in-memory payload without invoking argparse or HTTP."""
    ensure_supported_pair(source_format, target_format)
    decode_keys = {"source_name", "project", "tags", "kind", "id_key", "validate"}
    encode_keys = {
        "pretty",
        "canonical",
        "id_key",
        "calendar_name",
        "generated_at",
        "reject_loss",
    }
    decoded, diagnostics = decode_text(
        source_format,
        content,
        **{key: value for key, value in options.items() if key in decode_keys},
    )
    encoded = encode_items(
        decoded,
        target_format,
        **{key: value for key, value in options.items() if key in encode_keys},
    )
    return ConversionResult(encoded, len(decoded), diagnostics)


def ensure_supported_pair(source_format, target_format):
    """Fail unless a canonical source-target pair is explicitly supported."""
    if source_format not in SOURCE_FORMATS:
        raise UnknownFormatError(
            "Unknown source format %r. Known source formats: %s."
            % (source_format, ", ".join(SOURCE_FORMATS))
        )
    if target_format not in TARGET_FORMATS:
        if target_format in CANONICAL_FORMATS:
            raise UnsupportedConversionError(
                "Unsupported conversion: %s -> %s." % (source_format, target_format)
            )
        raise UnknownFormatError(
            "Unknown target format %r. Known target formats: %s."
            % (target_format, ", ".join(TARGET_FORMATS))
        )
    if (source_format, target_format) not in SUPPORTED_PAIRS:
        raise UnsupportedConversionError(
            "Unsupported conversion: %s -> %s." % (source_format, target_format)
        )


def items_from_markdown_task_list_text(
    text, project=None, kind="T", tags=None, source=None, github_refs=False
):
    """Decode Markdown checkbox-list entries into shared task items."""
    status_map = {" ": "[ ]", "x": "[x]", "X": "[x]", "-": "[-]", "/": "[/]"}
    task_re = re.compile(
        r"^(?P<indent>\s*)[-*+]\s+\[(?P<check>[xX \-/])\]\s+(?P<title>.+)$"
    )
    github_ref_re = re.compile(r"#(\d+)")
    items = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = task_re.match(line)
        if not match:
            continue
        raw_title = match.group("title").strip()
        title = raw_title
        details = OrderedDict()
        if source:
            details["source"] = [source]
        if project:
            details["project"] = [project]
        for tag in tags or ():
            details.setdefault("tag", []).append(tag)
        if github_refs:
            refs = github_ref_re.findall(raw_title)
            title = github_ref_re.sub("", raw_title).strip()
            for ref in refs:
                details.setdefault("ref", []).append(
                    "github-%s" % ref if source == "github" else ref
                )
        slug = title.replace(" ", "_") if title else raw_title.replace(" ", "_")
        items.append(
            Item(
                status_map.get(match.group("check"), "[ ]"),
                kind,
                slug,
                details,
                line=line_no,
            )
        )
    return items


def _stable_id(prefix, seed):
    return prefix + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _todo_item(raw, source, line_no, project=None, tags=None):
    text = raw.strip()
    if not text:
        return None
    completed = text.startswith("x ")
    if completed:
        text = text[2:].lstrip()
    details = OrderedDict()
    date_tokens = []
    tokens = text.split()
    if completed:
        while tokens and _TODO_DATE_RE.fullmatch(tokens[0]):
            date_tokens.append(tokens.pop(0))
            if len(date_tokens) == 2:
                break
    priority = None
    if tokens:
        priority_match = _TODO_PRIORITY_RE.fullmatch(tokens[0])
        if priority_match:
            priority = priority_match.group(1)
            tokens.pop(0)
    if not completed and tokens and _TODO_DATE_RE.fullmatch(tokens[0]):
        date_tokens.append(tokens.pop(0))

    projects = []
    contexts = []
    metadata = OrderedDict()
    title_tokens = []
    for token in tokens:
        if len(token) > 1 and token.startswith("+"):
            projects.append(token[1:])
            continue
        if len(token) > 1 and token.startswith("@"):
            contexts.append(token[1:])
            continue
        match = _TODO_KV_RE.fullmatch(token)
        if match:
            key, value = match.groups()
            if key == "project":
                projects.append(value)
                continue
            if key == "context":
                contexts.append(value)
                continue
            if key == "pri" and re.fullmatch(r"[A-Z]", value) and priority is None:
                priority = value
            else:
                metadata.setdefault(key, []).append(value)
            continue
        title_tokens.append(token)
    if priority is not None:
        details["priority"] = [priority]
    text = " ".join(title_tokens)
    if project:
        projects.insert(0, project)
    if projects:
        details.setdefault("project", []).extend(projects)
    if contexts:
        details.setdefault("context", []).extend(contexts)
    for key, values in metadata.items():
        details.setdefault(key, []).extend(values)
    if tags:
        details["tag"] = list(tags)
    if completed and date_tokens:
        details["done"] = [date_tokens[0]]
        if len(date_tokens) > 1:
            details["created"] = [date_tokens[1]]
    elif date_tokens:
        details["created"] = [date_tokens[0]]
    if "source" not in details:
        details["source"] = ["todo.txt"]
    if "id" not in details:
        details["id"] = [_stable_id("todo_", "%s:%s:%s" % (source, line_no, raw))]
    return Item(
        "[x]" if completed else "[ ]", "T", text or "Untitled", details, line=line_no
    )


def items_from_todo_text(text, source="content", project=None, tags=None):
    """Decode todo.txt-style lines into shared task items."""
    items = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        item = _todo_item(raw, source, line_no, project=project, tags=tags)
        if item is not None:
            items.append(item)
    return items
