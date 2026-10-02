"""Surface-neutral resolution of one Quick input; no persistence or UI logic."""

from dataclasses import dataclass

from .ids import duplicate_id_diagnostics
from .model import Item
from .parser import parse_text
from .serializer import item_to_line
from .shorthand import parse_capture


class QuickInputError(ValueError):
    """Invalid Quick input, with authoritative Format diagnostics when present."""

    def __init__(self, message, diagnostics=()):
        self.diagnostics = list(diagnostics)
        super().__init__(message)


@dataclass
class QuickInput:
    item: Item
    mode: str
    diagnostics: list


def resolve_quick_input(
    text,
    *,
    id_key="id",
    today=None,
    shorthand=True,
    shorthand_item=None,
    extra_details=None,
    merge_tags=False,
):
    """Resolve shorthand or a complete record, rejecting malformed record intent.

    A leading ``[`` reserves Format intent, matching the parser's status
    entry point. It is only a safety discriminator, never a grammar/parser.
    Unknown statuses, types and malformed details go to the normal parser
    and cannot fall back to shorthand. Quick accepts one physical line.

    ``shorthand_item`` carries an adapter's existing explicit flags/defaults.
    Full records ignore those defaults. Context details fill absent fields.
    IDs, workspace references and writes remain the mutation layer's job.
    """
    raw = str(text or "")
    if len(raw.splitlines()) > 1 or any(
        c in raw for c in "\r\n\v\f\x1c\x1d\x1e\u0085\u2028\u2029"
    ):
        raise QuickInputError(
            "Quick accepts one line only; use explicit import for multiple lines."
        )
    raw = raw.strip()
    if not raw:
        raise QuickInputError("text is required.")
    if raw.startswith("["):
        items, diagnostics = parse_text(
            raw + "\n", id_key=id_key, check_references=False
        )
        errors = [d for d in diagnostics if d.severity == "error"]
        if errors or len(items) != 1:
            message = "; ".join("%s: %s" % (d.code, d.message) for d in errors)
            raise QuickInputError(
                message or "Expected one complete life.txt record.", diagnostics
            )
        item = items[0]
        mode = "full_line"
    else:
        item = shorthand_item or Item("[ ]", "T", raw)
        item.title = raw
        if shorthand:
            title, details = parse_capture(raw, today=today, strict_dates=True)
            if not title:
                raise QuickInputError(
                    "Capture shorthand consumed the whole title. Add a title or use --no-shorthand."
                )
            item.title = title
            for key, values in details.items():
                if merge_tags and key == "tag":
                    existing = item.details.setdefault(key, [])
                    for value in values:
                        if value not in existing:
                            existing.append(value)
                elif key not in item.details:
                    item.details[key] = list(values)
        mode = "shorthand"
        diagnostics = []
    if extra_details is not None and not isinstance(extra_details, dict):
        raise QuickInputError("details must be an object of arrays of strings.")
    for key, values in (extra_details or {}).items():
        if (
            not isinstance(key, str)
            or not isinstance(values, list)
            or not all(isinstance(v, str) for v in values)
        ):
            raise QuickInputError("details must be an object of arrays of strings.")
        if key not in item.details:
            item.details[key] = list(values)
    # Validate even context-provided fields and shorthand values through the
    # same serializer/parser. No adapter can bypass malformed full-line safety.
    _items, diagnostics = parse_text(
        item_to_line(item) + "\n", id_key=id_key, check_references=False
    )
    errors = [d for d in diagnostics if d.severity == "error"]
    if errors:
        raise QuickInputError(
            "; ".join("%s: %s" % (d.code, d.message) for d in errors), diagnostics
        )
    duplicates = duplicate_id_diagnostics([item], key=id_key)
    if duplicates:
        raise QuickInputError(
            "Authoritative write rejected: workspace IDs must be unique.", duplicates
        )
    return QuickInput(item, mode, diagnostics)
