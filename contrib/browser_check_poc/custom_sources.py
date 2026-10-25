"""Corresponding source for the fixed HKSCS-free distribution, never approval."""

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile

from contrib.browser_check_poc import hkscs_free
from contrib.browser_check_poc import source_delivery as upstream

SOURCE = Path(__file__).resolve().parent
LOCK = "hkscs-distribution-lock.json"


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(cache, destination):
    """Return derived lock; caller must compare it with the reviewed fixed lock."""
    cache, destination = Path(cache), Path(destination)
    lock = upstream.load_lock(SOURCE)
    upstream.validate_cache(cache, lock)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp) / "stage"
        root = hkscs_free.prepare_build(cache, stage)
        destination.mkdir(parents=True)
        entries = []
        for original in lock["archives"]:
            if not original["ship_source"]:
                continue
            entry = copy.deepcopy(original)
            target = destination / entry["file"]
            if entry["id"] == "cpython":
                target.write_bytes(
                    (stage / "curated/cpython-hkscs-free.tar.gz").read_bytes()
                )
                entry["base_upstream_sha256"] = original["sha256"]
                entry["base_upstream_url"] = entry.pop("url")
                entry["derivation"] = (
                    "seven HKSCS files removed; encoding aliases removed"
                )
                entry["required_members"] = {
                    k: v
                    for k, v in entry["required_members"].items()
                    if k not in hkscs_free.REMOVED
                }
                entry["required_members"]["Lib/encodings/aliases.py"] = json.loads(
                    (stage / "curated/source-removal.json").read_text()
                )["aliases_sha256"]
            elif entry["id"] == "pyodide":
                files = {}
                with tarfile.open(cache / original["file"]) as archive:
                    for member in archive:
                        if member.isfile():
                            name = member.name.removeprefix(original["root"] + "/")
                            files[name] = ((root / name).read_bytes(), member.mode)
                files["tools/hkscs_free_build.py"] = (
                    (root / "tools/hkscs_free_build.py").read_bytes(),
                    0o644,
                )
                files["tools/hkscs_free_build.LICENSE"] = (
                    (SOURCE.parents[1] / "LICENSE").read_bytes(),
                    0o644,
                )
                files["LIFETXT_MODIFICATIONS.md"] = (
                    b"# lifetxt modifications, 2026-10-25\n\n"
                    b"HKSCS builtin disabled; curated CPython and local source recipes;\n"
                    b"single-write JS/stdlib helper. Original modified files retain MPL-2.0.\n"
                    b"tools/hkscs_free_build.py is copied from lifetxt under the MIT terms\n"
                    b"and copyright notice in tools/hkscs_free_build.LICENSE.\n",
                    0o644,
                )
                buffer = io.BytesIO()
                with gzip.GzipFile(
                    fileobj=buffer, mode="wb", filename="", mtime=0
                ) as compressed:
                    with tarfile.open(fileobj=compressed, mode="w") as archive:
                        for name, (data, mode) in sorted(files.items()):
                            info = tarfile.TarInfo(original["root"] + "/" + name)
                            info.size, info.mode = len(data), mode
                            archive.addfile(info, io.BytesIO(data))
                target.write_bytes(buffer.getvalue())
                entry["base_upstream_sha256"] = original["sha256"]
                entry["base_upstream_url"] = entry.pop("url")
                entry["derivation"] = (
                    "HKSCS disabled; curated/local source recipes; single-write build helper"
                )
                for name in (
                    "Makefile",
                    "cpython/Makefile",
                    "cpython/Setup.local",
                    "tools/hkscs_free_build.py",
                ):
                    entry["required_members"][name] = sha((root / name).read_bytes())
                for name in (
                    "tools/hkscs_free_build.LICENSE",
                    "LIFETXT_MODIFICATIONS.md",
                ):
                    entry["required_members"][name] = sha(files[name][0])
            else:
                target.write_bytes((cache / original["file"]).read_bytes())
            if entry["id"] in {"cpython", "pyodide"}:
                entry["correspondence_basis"] = (
                    "custom-profile-derived-from-fixed-upstream"
                )
                entry["version"] += " / lifetxt-hkscs-free-1 (modified)"
            entry["bytes"] = target.stat().st_size
            entry["sha256"] = sha(target.read_bytes())
            entries.append(entry)
    return {
        "schema_version": 1,
        "runtime_profile": "lifetxt-hkscs-free-1",
        "archives": entries,
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
    }


def load_lock():
    lock = json.loads((SOURCE / LOCK).read_text(encoding="utf-8"))
    if (
        lock["schema_version"] != 1
        or lock["runtime_profile"] != "lifetxt-hkscs-free-1"
        or (
            lock["complete_distribution_audit"] is not False
            or lock["public_distribution_approved"] is not False
        )
    ):
        raise ValueError("custom source lock cannot grant approval")
    if {e["id"] for e in lock["archives"]} != upstream.SOURCE_IDS - {
        "upstream-core"
    } or len(lock["archives"]) != 10:
        raise ValueError("custom profile requires exactly ten source archives")
    originals = {e["id"]: e for e in upstream.load_lock(SOURCE)["archives"]}
    for entry in lock["archives"]:
        original = originals[entry["id"]]
        if entry["ship_source"] is not True:
            raise ValueError("all ten custom source archives must be delivered")
        if entry["id"] not in {"cpython", "pyodide"}:
            if entry != original:
                raise ValueError("unchanged component source differs from upstream pin")
        elif (
            entry["file"] != original["file"]
            or entry["root"] != original["root"]
            or entry["base_upstream_sha256"] != original["sha256"]
            or entry["sha256"] == original["sha256"]
            or entry["correspondence_basis"]
            != "custom-profile-derived-from-fixed-upstream"
        ):
            raise ValueError("derived archive lost its fixed upstream/custom identity")
        if entry["id"] in {"cpython", "pyodide"}:
            changed = (
                (hkscs_free.REMOVED | {"Lib/encodings/aliases.py"})
                if entry["id"] == "cpython"
                else {"Makefile", "cpython/Makefile", "cpython/Setup.local"}
            )
            if any(
                entry["required_members"].get(k) != v
                for k, v in original["required_members"].items()
                if k not in changed
            ):
                raise ValueError(
                    "derived source must preserve retained original licence/member hashes"
                )
        if entry["id"] == "pyodide" and entry["required_members"].get(
            "tools/hkscs_free_build.LICENSE"
        ) != sha((SOURCE.parents[1] / "LICENSE").read_bytes()):
            raise ValueError("custom build helper requires its original MIT notice")
    return lock


def validate(directory, lock=None):
    directory = Path(directory)
    lock = load_lock() if lock is None else lock
    for entry in lock["archives"]:
        path = directory / entry["file"]
        upstream.verify_bytes(path, entry)
        members = upstream.read_members(path, entry["root"], entry["required_members"])
        if any(sha(members[k]) != v for k, v in entry["required_members"].items()):
            raise ValueError("custom source member mismatch")
        if entry["id"] == "cpython":
            with tarfile.open(path) as archive:
                names = {m.name.removeprefix(entry["root"] + "/") for m in archive}
            if names.intersection(hkscs_free.REMOVED):
                raise ValueError("HKSCS source payload in custom bundle")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--write-lock",
        action="store_true",
        help="explicit maintenance operation; resulting lock requires PR review",
    )
    args = parser.parse_args()
    generated = prepare(args.upstream_cache, args.output)
    if args.write_lock:
        (SOURCE / LOCK).write_bytes(json_bytes(generated))
    elif generated != load_lock():
        raise ValueError("derived source bytes differ from reviewed custom lock")
    validate(args.output, generated)
