"""Recheck pinned source-specific ICU evidence; do not grant or authenticate permission."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

from contrib.browser_check_poc.source_delivery import (
    SOURCE,
    load_lock,
    read_members,
    verify_bytes,
    safe_path,
)

IDS = {"icu-xml", "icu-license", "icu-repository-readme", "icu-charset-readme"}


def evidence(source=SOURCE):
    value = json.loads(
        (source / "notices/mapping-attribution.json").read_text("utf-8")
    )["permission_evidence"]
    revision = value["icu_data_commit"]
    if value["schema_version"] != 1 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid permission evidence revision")
    if len(safe_path(value["license_notice"]).parts) != 1:
        raise ValueError("Unsafe licence notice path")
    rows = value["inputs"]
    if len(rows) != len(IDS) or {r["id"] for r in rows} != IDS:
        raise ValueError("Missing or duplicate permission evidence")
    names = set()
    prefix = f"https://raw.githubusercontent.com/unicode-org/icu-data/{revision}/"
    for row in rows:
        name = row["file"]
        if (
            Path(name).name != name
            or "\\" in name
            or ":" in name
            or name in names
            or not row["url"].startswith(prefix)
            or "/../" in row["url"]
            or type(row["bytes"]) is not int
            or not 0 < row["bytes"] < 1_000_000
            or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        ):
            raise ValueError("Unsafe or unpinned permission input")
        names.add(name)
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect of pinned permission evidence")


def fetch(cache, source=SOURCE):
    """Explicit maintainer download of data only; no mail or upstream writes."""
    value = evidence(source)
    cache.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirect())
    for row in value["inputs"]:
        target = cache / row["file"]
        if target.exists() or target.is_symlink():
            verify_bytes(target, row)
            continue
        with opener.open(row["url"], timeout=45) as response:
            raw = response.read(row["bytes"] + 1)
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Changed permission evidence bytes")
        with target.open("xb") as stream:
            stream.write(raw)


def compare_xml(cpython, upstream):
    if cpython != upstream + b"\n":
        raise ValueError("ICU/CPython XML differs beyond the locked single trailing LF")
    return "exactly one additional trailing LF in CPython; all other bytes identical"


def verify(cache, source_cache, source=SOURCE, *, custom_source_profile=False):
    value = evidence(source)
    data = {}
    for row in value["inputs"]:
        path = cache / row["file"]
        verify_bytes(path, row)
        data[row["id"]] = path.read_bytes()
    if custom_source_profile:
        from contrib.browser_check_poc.custom_sources import load_lock as custom_lock

        lock = custom_lock()
    else:
        lock = load_lock(source)
    cpython = next(e for e in lock["archives"] if e["id"] == "cpython")
    path = source_cache / cpython["file"]
    verify_bytes(path, cpython)
    member = value["cpython_member"]
    raw = read_members(path, cpython["root"], [member])[member]
    if hashlib.sha256(raw).hexdigest() != cpython["required_members"][member]:
        raise ValueError("CPython source member differs from locked evidence")
    comparison = compare_xml(raw, data["icu-xml"])
    if (source / "notices" / value["license_notice"]).read_bytes() != data[
        "icu-license"
    ]:
        raise ValueError("Shipped ICU licence differs from pinned upstream grant")
    if b"released under [LICENSE]" not in data["icu-repository-readme"]:
        raise ValueError("Missing official repository licence scope declaration")
    result = {
        "icu_data_commit": value["icu_data_commit"],
        "cpython_archive_sha256": cpython["sha256"],
        "cpython_xml_sha256": hashlib.sha256(raw).hexdigest(),
        "icu_xml_sha256": hashlib.sha256(data["icu-xml"]).hexdigest(),
        "comparison": comparison,
        "licence_bytes_match": True,
        "independent_permission_acceptance": "pending",
        "hkscs_new_permission_received": False,
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
    }
    if custom_source_profile:
        result.update(
            runtime_profile="lifetxt-hkscs-free-1",
            base_upstream_cpython_sha256=cpython["base_upstream_sha256"],
            source_member=member,
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "verify"))
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument(
        "--custom-source-profile",
        action="store_true",
        help="verify the fixed curated CPython archive instead of the official upstream input",
    )
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args.cache)
    else:
        if args.source_cache is None:
            parser.error("verify requires --source-cache")
        print(
            json.dumps(
                verify(
                    args.cache,
                    args.source_cache,
                    custom_source_profile=args.custom_source_profile,
                ),
                indent=2,
            )
        )
