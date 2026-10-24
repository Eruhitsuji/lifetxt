"""Validate the bounded notice inventory, never certify legal completeness."""

import hashlib
import json
import html
from urllib.parse import urlsplit
from pathlib import Path


def validate_notices(source, runtime=None):
    directory = source / "notices"
    provenance = json.loads((directory / "provenance.json").read_text("utf-8"))
    inventory = json.loads((directory / "components.json").read_text("utf-8"))
    if provenance["complete_distribution_audit"] is not False or (
        inventory["complete_distribution_audit"] is not False
        or inventory["public_distribution_approved"] is not False
        or not inventory["remaining_gates"]
    ):
        raise ValueError("This partial investigation cannot approve distribution")
    names = []
    for entry in provenance["files"]:
        name = entry["file"]
        if (
            Path(name).name != name
            or "\\" in name
            or ":" in name
            or name in names
            or name
            in (
                "README.md",
                "provenance.json",
                "components.json",
                "index.html",
                "mapping-attribution.json",
            )
        ):
            raise ValueError("Notice name must be a unique basename")
        url = urlsplit(entry["source_url"])
        if (
            url.scheme != "https"
            or url.hostname not in {"raw.githubusercontent.com", "www.unicode.org"}
            or url.username
            or url.password
            or url.port not in (None, 443)
            or url.fragment
        ):
            raise ValueError("Notice provenance must identify the upstream snapshot")
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != (entry["stored_sha256"])
        ):
            raise ValueError("Notice hash mismatch: " + name)
        names.append(name)
    if not names:
        raise ValueError("Notice inventory must not be empty")
    for component in inventory["components"]:
        if component["notice"] is not None and component["notice"] not in names:
            raise ValueError("Component refers to a missing notice")
    if runtime is not None:
        expected_names = {
            "runtime/" + name
            for name in (
                "pyodide.mjs",
                "pyodide.asm.mjs",
                "pyodide.asm.wasm",
                "python_stdlib.zip",
                "pyodide-lock.json",
            )
        }
        if set(inventory["runtime_observations"]["runtime_files"]) != expected_names:
            raise ValueError("Runtime inventory must cover all five shipped files")
        for path, expected in inventory["runtime_observations"][
            "runtime_files"
        ].items():
            name = Path(path).name
            if path != "runtime/" + name:
                raise ValueError("Runtime inventory paths must be flat")
            data = (runtime / name).read_bytes()
            if len(data) != expected["bytes"] or (
                hashlib.sha256(data).hexdigest() != expected["sha256"]
            ):
                raise ValueError("Runtime differs from retained inventory: " + name)
    return sorted(
        names
        + [
            "README.md",
            "provenance.json",
            "components.json",
            "mapping-attribution.json",
        ]
    )


def render_notice_index(source):
    """Every retained notice is discoverable, including unmapped source notices."""
    directory = source / "notices"
    provenance = json.loads((directory / "provenance.json").read_text("utf-8"))
    inventory = json.loads((directory / "components.json").read_text("utf-8"))
    rows = []
    for entry in provenance["files"]:
        components = [
            c["name"]
            + " ("
            + str(c["version"])
            + ")"
            + (" — section: " + c["notice_section"] if c.get("notice_section") else "")
            for c in inventory["components"]
            if c["notice"] == entry["file"]
        ]
        label = "; ".join(components) or "Additional source notice / 追加の出典表示"
        rows.append(
            '<li><a href="'
            + html.escape(entry["file"], quote=True)
            + '">'
            + html.escape(entry["file"])
            + "</a> — "
            + html.escape(label)
            + "</li>"
        )
    return (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Third-party notices | lifetxt</title></head><body>
<h1>Third-party notices / 第三者ライセンス一覧</h1>
<p>These source notices preserve their original terms. Inclusion is not exhaustive binary attribution or publication clearance.</p>
<p><a href="README.md">Inventory guide / 説明</a> · <a href="components.json">Components, versions and evidence / 構成と確認範囲</a> · <a href="mapping-attribution.json">Mapping source and terms assessment</a> · <a href="provenance.json">Notice provenance and hashes</a> · <a href="../sources/index.html">Source downloads / ソース取得</a></p><ul>"""
        + "".join(rows)
        + "</ul></body></html>\n"
    )


def write_notice_index(destination, source):
    (destination / "index.html").write_text(
        render_notice_index(source), encoding="utf-8", newline="\n"
    )


def audit_notice_index(destination, source):
    if (destination / "index.html").read_bytes() != render_notice_index(source).encode(
        "utf-8"
    ):
        raise ValueError("Notice index missing, changed or incomplete")

    from scripts.check_website import Document

    links = Document((destination / "index.html").read_text("utf-8")).links
    names = validate_notices(source)
    if not set(names).issubset(set(links)):
        raise ValueError("Notice index does not link every notice and metadata file")
    for name in names:
        if not (destination / name).is_file():
            raise ValueError("Notice index target is missing: " + name)
