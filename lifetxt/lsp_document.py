"""In-memory documents and explicit Core/code-point to LSP/UTF-16 mapping."""

from dataclasses import dataclass, field
from bisect import bisect_right
import re

from .parser import parse_text
from .safety_foundation import canonical_issues, format_version_report

MAX_DOCUMENT_BYTES = 256 * 1024
MAX_DOCUMENTS = 32
MAX_RESULTS = 200


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


def codepoint_offset(text, units):
    if type(units) is not int or units < 0:
        raise ValueError("Invalid UTF-16 character")
    count = 0
    for index, char in enumerate(text):
        if count == units:
            return index
        count += utf16_length(char)
        if count > units:
            raise ValueError("Position splits a UTF-16 surrogate pair")
    if count == units:
        return len(text)
    raise ValueError("Position is outside the line")


@dataclass
class Document:
    uri: str
    version: int
    text: str
    id_key: str = "id"
    check_links: bool = True
    lines: list = field(init=False)
    result: object = field(init=False)
    logical_positions: dict = field(init=False)
    core_origins: list = field(init=False)

    def __post_init__(self):
        if (
            not isinstance(self.text, str)
            or len(self.text.encode("utf-8")) > MAX_DOCUMENT_BYTES
        ):
            raise ValueError("Document exceeds 256 KiB UTF-8 limit")
        if type(self.version) is not int:
            raise ValueError("Document version must be an integer")
        self.lines = re.split(r"\r\n|\r|\n", self.text)
        # Core strips a file BOM at the file-reading boundary. Mirror that
        # boundary in memory, while retaining it in the position map.
        self.result = parse_text(
            self.text.removeprefix("\ufeff"),
            id_key=self.id_key,
            check_ids=self.check_links,
            check_references=self.check_links,
        )
        self.logical_positions = {}
        plain = self.text.removeprefix("\ufeff")
        chunks = plain.splitlines(keepends=True)
        rows = plain.splitlines()
        lsp_starts = [0] + [m.end() for m in re.finditer(r"\r\n|\r|\n", plain)]
        self.core_origins = []
        source_offset = 0
        for chunk in chunks:
            actual_row = bisect_right(lsp_starts, source_offset) - 1
            self.core_origins.append(
                (actual_row, source_offset - lsp_starts[actual_row])
            )
            source_offset += len(chunk)
        if not self.core_origins:
            self.core_origins = [(0, 0)]
        row = 0
        while row < len(rows):
            first = row
            locations = []
            logical_offset = 0
            while True:
                text = rows[row]
                indent = len(text) - len(text.lstrip(" ")) if row != first else 0
                tail = text.rstrip(" ")
                continued = tail.endswith("\\")
                end = len(tail) - 1 if continued else len(text)
                length = max(0, end - indent)
                locations.append((logical_offset, logical_offset + length, row, indent))
                logical_offset += length
                row += 1
                if not continued or row >= len(rows):
                    break
            self.logical_positions[first] = locations

    def offset(self, position):
        line = position["line"]
        if type(line) is not int or not 0 <= line < len(self.lines):
            raise ValueError("Position is outside the document")
        return line, codepoint_offset(self.lines[line], position["character"])

    def position(self, line, column, logical=True):
        row = max(0, min((line or 1) - 1, len(self.core_origins) - 1))
        offset = max(0, (column or 1) - 1)
        if logical and row in self.logical_positions:
            segments = self.logical_positions[row]
            segment = next(
                (part for part in segments if part[0] <= offset < part[1]), segments[-1]
            )
            begin, end, row, indent = segment
            offset = indent + max(0, min(offset, end) - begin)
        row, base = self.core_origins[row]
        offset += base
        if row == 0 and self.text.startswith("\ufeff"):
            offset += 1
        return {"line": row, "character": utf16_length(self.lines[row][:offset])}

    def diagnostics(self, extra=()):
        output = []
        for d in [*self.result[1], *extra][:MAX_RESULTS]:
            physical = d.code in {"E019", "E020", "E021", "E022"}
            start = self.position(d.line, d.column, logical=not physical)
            # Preserve only supplied spans; convert joined logical columns
            # through the exact physical-character map.
            end = start
            if d.end_line is not None and d.end_column is not None:
                end = self.position(d.end_line, d.end_column, logical=not physical)
            if (end["line"], end["character"]) < (start["line"], start["character"]):
                end = start
            output.append(
                {
                    "range": {"start": start, "end": end},
                    "severity": {"error": 1, "warning": 2, "info": 3, "hint": 4}.get(
                        d.severity, 3
                    ),
                    "code": d.code,
                    "source": "lifetxt",
                    "message": d.message + ("\n" + d.hint if d.hint else ""),
                }
            )
        if (
            format_version_report(self.text.removeprefix("\ufeff"))["state"]
            == "unsupported"
        ):
            policy = next(
                d
                for d in canonical_issues(self.text.removeprefix("\ufeff"))
                if d["code"] == "F110"
            )
            point = self.position(1, 1)
            output.insert(
                0,
                {
                    "range": {"start": point, "end": point},
                    "severity": 1,
                    "code": "F110",
                    "source": "lifetxt",
                    "message": policy["message"] + "\n" + policy["hint"],
                },
            )
        return output[:MAX_RESULTS]
