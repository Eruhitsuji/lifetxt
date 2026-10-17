"""Explicit open-buffer workspace; never discovers or reads disk files."""

from collections import defaultdict

from .ids import duplicate_id_diagnostics
from .links import reference_diagnostics
from .model import Diagnostic
from .safety_foundation import format_version_report


def workspace_items(documents):
    return [
        item
        for doc in documents.values()
        if format_version_report(doc.text.removeprefix("\ufeff"))["state"]
        != "unsupported"
        for item in doc.result[0]
    ]


def workspace_diagnostics(documents, id_key):
    items = workspace_items(documents)
    # Source is an opaque client URI, used solely to route diagnostics back.
    for document in documents.values():
        for item in document.result[0]:
            item.source = document.uri
    grouped = defaultdict(list)
    try:
        diagnostics = duplicate_id_diagnostics(
            items, key=id_key
        ) + reference_diagnostics(items, key=id_key)
        for diagnostic in diagnostics:
            grouped[diagnostic.source].append(diagnostic)
    except RecursionError:
        # Core uses recursive graph traversal. Do not crash or silently claim
        # a complete graph validation for deeply nested but bounded documents.
        for uri in documents:
            grouped[uri].append(
                Diagnostic(
                    "error",
                    "LSP001",
                    "Open-buffer reference graph exceeds the Core analysis depth. Local syntax diagnostics remain available.",
                    line=1,
                    column=1,
                    hint="Close unrelated buffers or simplify the reference chain.",
                )
            )
    return grouped
