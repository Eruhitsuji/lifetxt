"""Hash-locked source acquisition and offline source delivery; no legal clearance."""

import argparse
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit
import zipfile

SOURCE = Path(__file__).resolve().parent
PYODIDE_COMMIT = "b1e4fcc2488962f6360a97f19b9982d6fdb5d16f"
SOURCE_IDS = {
    "pyodide",
    "hiwire",
    "cpython",
    "emscripten",
    "libffi",
    "xz",
    "zstd",
    "sqlite",
    "zlib",
    "bzip2",
    "upstream-core",
}
HOSTS = {
    "github.com",
    "codeload.github.com",
    "www.python.org",
    "www.sqlite.org",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}
METADATA = {
    "index.html",
    "source-lock.json",
    "SOURCE_DELIVERY.md",
    "source-provenance.json",
}


def safe_path(name):
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or ":" in name
        or path.is_absolute()
        or any(p in (".", "..") for p in name.split("/"))
    ):
        raise ValueError("Unsafe source path")
    return path


def check_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Source URL must use an approved HTTPS origin")


def load_lock(source=SOURCE):
    lock = json.loads((source / "source-lock.json").read_text("utf-8"))
    entries = lock["archives"]
    if (
        lock["schema_version"] != 1
        or lock["pyodide_commit"] != PYODIDE_COMMIT
        or lock["pyodide"] != "314.0.7"
        or lock["complete_distribution_audit"] is not False
        or lock["public_distribution_approved"] is not False
    ):
        raise ValueError("Source inventory cannot approve publication")
    if len(entries) != len(SOURCE_IDS) or {e["id"] for e in entries} != SOURCE_IDS:
        raise ValueError("Source inventory must cover all retained components")
    names = []
    for entry in entries:
        name = entry["file"]
        if len(safe_path(name).parts) != 1 or name in names or name in METADATA:
            raise ValueError("Source archive requires a unique basename")
        names.append(name)
        check_url(entry["url"])
        if (
            not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
            or type(entry["bytes"]) is not int
            or not 0 < entry["bytes"] < 80_000_000
        ):
            raise ValueError("Source archive must have bounded size and SHA256")
        if (
            type(entry["ship_source"]) is not bool
            or entry["ship_source"] != (entry["id"] != "upstream-core")
            or not entry["required_members"]
        ):
            raise ValueError("Archive source scope or required files missing")
        safe_path(entry["root"])
        for member, sha in entry["required_members"].items():
            safe_path(member)
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise ValueError("Source member hash missing")
    return lock


def verify_bytes(path, entry):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["bytes"]:
        raise ValueError("Missing or wrong-size source archive: " + entry["file"])
    with path.open("rb") as stream:
        sha = (
            hashlib.file_digest(stream, "sha256").hexdigest()
            if hasattr(hashlib, "file_digest")
            else hashlib.sha256(stream.read()).hexdigest()
        )
    if sha != entry["sha256"]:
        raise ValueError("Source archive hash mismatch: " + entry["file"])


def read_members(path, root, wanted):
    """Read selected regular files without extracting or executing an archive."""
    targets = {root + "/" + name: name for name in wanted}
    result = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.filename in targets:
                    if (
                        member.filename in result
                        or member.is_dir()
                        or stat.S_ISLNK(member.external_attr >> 16)
                    ):
                        raise ValueError("Duplicate/invalid archive member")
                    result[member.filename] = archive.read(member)
    else:
        with tarfile.open(path) as archive:
            for member in archive:
                if member.name in targets:
                    if member.name in result or not member.isfile():
                        raise ValueError("Duplicate/non-regular source member")
                    result[member.name] = archive.extractfile(member).read()
    if set(result) != set(targets):
        raise ValueError("Source archive missing required licence/patch/member")
    return {targets[name]: data for name, data in result.items()}


def validate_cache(cache, lock, *, include_core=False):
    for entry in lock["archives"]:
        if not entry["ship_source"] and not include_core:
            continue
        path = cache / entry["file"]
        verify_bytes(path, entry)
        members = read_members(path, entry["root"], entry["required_members"])
        if any(
            hashlib.sha256(members[n]).hexdigest() != sha
            for n, sha in entry["required_members"].items()
        ):
            raise ValueError("Licence/patch/source member hash mismatch")


def render_index(lock, bundled=False):
    rows = []
    for e in lock["archives"]:
        if not e["ship_source"]:
            continue
        link = e["file"] if bundled else e["url"]
        rows.append(
            '<li><a href="'
            + html.escape(link, quote=True)
            + '">'
            + html.escape(e["id"] + " " + e["version"])
            + "</a><p>"
            + html.escape(e["license"])
            + "</p><p>SHA256: <code>"
            + e["sha256"]
            + "</code></p></li>"
        )
    return (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Runtime sources and licences | lifetxt</title></head><body>
<h1>Runtime sources and licences / ランタイムのソース・ライセンス</h1>
<p>Source Code Form for the retained Pyodide/hiwire MPL-2.0 components is available below. Their source remains governed by MPL-2.0; other source archives retain their own notices and terms. Full notices are inside each archive.</p>
<p>固定版のソースとライセンスを以下から取得できます。ソースは各ライセンスに従います。製品の公開審査は未完です。</p>
<p>These are upstream release/recipe sources, not a reproducible-build or full binary attribution attestation. No local modifications to runtime bytes are made; upstream build patches are retained in the Pyodide/hiwire archives. This preview is not approved for publication.</p>
<p>The source form of stdlib Python files, including generated configuration, is also present in <a href="../runtime/python_stdlib.zip">the exact shipped stdlib ZIP</a>.</p>
<p><a href="source-lock.json">Versions, hashes and required source/patch members</a> · <a href="SOURCE_DELIVERY.md">Delivery status / 検証範囲</a> · <a href="source-provenance.json">Source correspondence evidence / 対応根拠</a> · <a href="../notices/index.html">All third-party notices / 全ライセンス</a></p><ul>"""
        + "".join(rows)
        + "</ul></body></html>\n"
    )


def write_delivery(destination, source=SOURCE, cache=None):
    lock = load_lock(source)
    if cache is not None:
        validate_cache(Path(cache), lock)
    destination.mkdir()
    (destination / "index.html").write_text(
        render_index(lock, cache is not None), encoding="utf-8"
    )
    for name in ("source-lock.json", "SOURCE_DELIVERY.md", "source-provenance.json"):
        shutil.copyfile(source / name, destination / name)
    if cache is not None:
        for e in lock["archives"]:
            if e["ship_source"]:
                shutil.copyfile(Path(cache) / e["file"], destination / e["file"])


def audit_delivery(output, source=SOURCE):
    lock = load_lock(source)
    destination = output / "sources"
    names = {p.name for p in destination.iterdir()}
    archives = {e["file"] for e in lock["archives"] if e["ship_source"]}
    bundled = names == METADATA | archives
    if names != METADATA and not bundled:
        raise ValueError("Source delivery must contain all archives or metadata only")
    if any(p.is_symlink() or not p.is_file() for p in destination.iterdir()):
        raise ValueError("Source delivery must contain flat regular files")
    if (destination / "index.html").read_bytes() != render_index(lock, bundled).encode(
        "utf-8"
    ):
        raise ValueError("Source acquisition index mismatch")
    for name in ("source-lock.json", "SOURCE_DELIVERY.md", "source-provenance.json"):
        if (destination / name).read_bytes() != (source / name).read_bytes():
            raise ValueError("Source metadata mismatch")
    if bundled:
        validate_cache(destination, lock)
    return {
        "mode": "hash-verified-self-hosted-archives"
        if bundled
        else "pinned-upstream-acquisition-links",
        "archive_count": len(archives),
        "correspondence": "upstream-release-and-recipes; independent distribution review pending",
    }, {"sources/" + n for n in names}


class SourceRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_sources(cache, lock):
    """Explicit maintainer action only. Never run by build or browser Worker."""
    cache.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(SourceRedirect())
    for entry in lock["archives"]:
        target = cache / entry["file"]
        if target.exists() or target.is_symlink():
            verify_bytes(target, entry)
            continue
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with (
                temporary.open("wb") as stream,
                opener.open(entry["url"], timeout=45) as response,
            ):
                count = 0
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > entry["bytes"]:
                        raise ValueError("Source response exceeds locked size")
                    stream.write(block)
            verify_bytes(temporary, entry)
            # Refuse to replace a file created while the download was in flight.
            with target.open("xb") as final, temporary.open("rb") as stream:
                shutil.copyfileobj(stream, final)
        finally:
            temporary.unlink(missing_ok=True)
    validate_cache(cache, lock, include_core=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "verify"))
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    lock = load_lock()
    if args.command == "fetch":
        fetch_sources(args.cache, lock)
    else:
        validate_cache(args.cache, lock, include_core=True)
    print(
        "Locked source archives and required licence/patch members verified; publication remains blocked."
    )
