"""Website parser-only adapter; same Core diagnostic contract as the PoC (#1399)."""

import json

import lifetxt
from lifetxt.diagnostic_contract import diagnostics_to_output
from lifetxt.parser import parse_text

MAX_BYTES = 16_384
MAX_DIAGNOSTICS = 100


def check_text(text):
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("input exceeds candidate 16384-byte limit")
    parsed = parse_text(text)
    items, diagnostics = parsed
    return {
        "scope": "parser-and-item-validator-only",
        "engine_version": lifetxt.__version__,
        "format_version_state": parsed.format_version_state,
        "items": len(items),
        "supported_format": parsed.format_version_state != "unsupported",
        "valid": parsed.format_version_state != "unsupported"
        and not any(d.severity == "error" for d in diagnostics),
        "diagnostic_count": len(diagnostics),
        "truncated": len(diagnostics) > MAX_DIAGNOSTICS,
        "diagnostics": diagnostics_to_output(diagnostics[:MAX_DIAGNOSTICS]),
    }


def check_json(text):
    return json.dumps(check_text(text), ensure_ascii=False)
