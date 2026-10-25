"""Check isolated artifact integrity; bind final artifacts to fixed sources and independent review evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import tempfile
import subprocess

from contrib.browser_check_poc import build as builder
from contrib.browser_check_poc.notice_inventory import (
    validate_notices,
    audit_notice_index,
)
from contrib.browser_check_poc.publication_gate import evaluate
from contrib.browser_check_poc.artifact_documents import document_bytes
from scripts.check_website import Document


PINNED_LOCK_SHA256 = "03131c28d96b17f3d89d91e55b81ce29b4f57642d792f78b5f5195b44944d680"


def digest(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def audit(output, source=builder.SOURCE, review_record=None):
    """Return evidence, not legal clearance. Reject unlisted and changed bytes."""
    output = Path(output)
    if output.is_symlink():
        raise ValueError("Artifact root cannot be a symlink")
    output = output.resolve()
    files = list(output.rglob("*"))
    if any(f.is_symlink() for f in files):
        raise ValueError("Symlinks are not distribution assets")
    source = Path(source)
    inventory = json.loads((source / "notices/components.json").read_text("utf-8"))
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    profile = manifest.get("profile", "poc")
    if profile == "website-checker-hkscs-free":
        from contrib.browser_check_poc.custom_distribution import audit as custom_audit

        return custom_audit(output, review_record)
    if profile not in {"poc", "website-checker"}:
        raise ValueError("Unknown artifact profile")
    assets = output / "checker" if profile == "website-checker" else output
    notices = validate_notices(source, assets / "runtime")
    audit_notice_index(assets / "notices", source)
    if manifest["pyodide"] != builder.VERSION:
        raise ValueError("Unexpected runtime version")
    if digest(source / "package-lock.json")["sha256"] != PINNED_LOCK_SHA256:
        raise ValueError("Lock differs from audited dependency set")
    package = json.loads((source / "package.json").read_text("utf-8"))
    lock = json.loads((source / "package-lock.json").read_text("utf-8"))
    if package["dependencies"] != {"pyodide": builder.VERSION} or (
        lock["packages"][""]["dependencies"] != package["dependencies"]
        or lock["packages"]["node_modules/pyodide"]["version"] != builder.VERSION
    ):
        raise ValueError("Package/lock/version mismatch")
    for name, entry in lock["packages"].items():
        if name and (
            not entry.get("integrity", "").startswith("sha512-")
            or not entry.get("resolved", "").startswith("https://registry.npmjs.org/")
        ):
            raise ValueError("Unpinned package source")
    from contrib.browser_check_poc.source_delivery import audit_delivery

    source_status, source_files = audit_delivery(assets, source)
    source_links = Document((assets / "sources/index.html").read_text("utf-8")).links
    if "../notices/index.html" not in source_links:
        raise ValueError("Source index must link the complete notice index")
    expected = (
        {
            "core.zip",
            "fixtures.json",
            "index.html",
            "ui.mjs",
            "worker.mjs",
            "engine.mjs",
            "adapter.py",
            "style.css",
        }
        | {"runtime/" + n for n in builder.RUNTIME_FILES}
        | {"notices/" + n for n in notices}
        | {"notices/index.html"}
        | source_files
    )
    if profile == "website-checker":
        from scripts.build_website_checker import COPY, SOURCE as checker_source, render
        from scripts.build_website import build as intro

        checker_assets = {
            "core.zip",
            "engine.mjs",
            "adapter.py",
            "limits.mjs",
            "worker.mjs",
            "ui.mjs",
            "checker.css",
        }
        expected = {
            "checker/" + n
            for n in (
                checker_assets
                | {"runtime/" + n for n in builder.RUNTIME_FILES}
                | {"notices/" + n for n in notices}
                | {"notices/index.html"}
                | source_files
            )
        }
        with tempfile.TemporaryDirectory() as d:
            reference = Path(d) / "intro"
            intro(reference)
            for file in reference.rglob("*"):
                if file.is_file():
                    name = file.relative_to(reference).as_posix()
                    expected.add(name)
                    if (output / name).read_bytes() != file.read_bytes():
                        raise ValueError("Website introduction asset changed: " + name)
        for lang in COPY:
            name = lang + "/check/index.html"
            expected.add(name)
            if (output / name).read_bytes() != render(lang).encode("utf-8"):
                raise ValueError("Checker page differs from reviewed renderer: " + name)
            links = Document((output / name).read_text("utf-8")).links
            if not {
                "../../checker/notices/index.html",
                "../../checker/sources/index.html",
            }.issubset(links):
                raise ValueError("Checker page must link notices and source downloads")
        for name in checker_assets - {"core.zip", "engine.mjs"}:
            if (assets / name).read_bytes() != (checker_source / name).read_bytes():
                raise ValueError("Checker asset differs from source: " + name)
    actual = {f.relative_to(output).as_posix() for f in files if f.is_file()}
    if actual != expected | {"manifest.json"} or set(manifest["files"]) != expected:
        raise ValueError("Artifact differs from fixed file allowlist")
    for name in sorted(expected):
        if digest(output / name) != manifest["files"][name]:
            raise ValueError("Artifact hash mismatch: " + name)
    for name, bound in inventory["runtime_observations"]["runtime_files"].items():
        if digest(assets / name) != bound:
            raise ValueError("Runtime differs from audited binary: " + name)
    for name in notices:
        expected_notice = (
            document_bytes(source / "notices" / name)
            if name == "README.md"
            else (source / "notices" / name).read_bytes()
        )
        if (assets / "notices" / name).read_bytes() != expected_notice:
            raise ValueError("Notice differs from reviewed source: " + name)
    poc_assets = (
        ("index.html", "ui.mjs", "worker.mjs", "engine.mjs", "adapter.py", "style.css")
        if profile == "poc"
        else ("engine.mjs",)
    )
    if (
        profile == "poc"
        and "notices/index.html"
        not in Document((assets / "index.html").read_text("utf-8")).links
    ):
        raise ValueError("PoC must link the complete notice index")
    for name in poc_assets:
        if digest(assets / name) != digest(source / name):
            raise ValueError("Asset differs from build source: " + name)
    if manifest["core_modules"] != [
        f"lifetxt/{n}.py" for n in sorted(builder.CORE_MODULES)
    ]:
        raise ValueError("Core module allowlist mismatch")
    if (assets / "core.zip").read_bytes() != builder.core_archive_bytes():
        raise ValueError("Core ZIP bytes differ from deterministic source archive")
    with zipfile.ZipFile(assets / "core.zip") as archive:
        expected_members = set(manifest["core_modules"]) | {"LICENSE"}
        if (
            len(archive.namelist()) != len(expected_members)
            or set(archive.namelist()) != expected_members
        ):
            raise ValueError("Unexpected Core ZIP members")
        for name in expected_members:
            path = builder.ROOT / name
            if name != "LICENSE" and (
                Path(name).parent.as_posix() != "lifetxt" or path.suffix != ".py"
            ):
                raise ValueError("Unexpected Core source path")
            if archive.read(name) != path.read_bytes():
                raise ValueError("Core ZIP source mismatch: " + name)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=builder.ROOT, text=True
    ).strip()
    if manifest["engine_base_revision"] != revision:
        raise ValueError("Artifact revision differs from current source checkout")
    clean = not subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "contrib/browser_check_poc",
            "scripts",
            "website",
            "lifetxt",
            "LICENSE",
        ],
        cwd=builder.ROOT,
        text=True,
    ).strip()
    mapping_bytes = (assets / "notices/mapping-attribution.json").read_bytes()
    if mapping_bytes != (source / "notices/mapping-attribution.json").read_bytes():
        raise ValueError("Packaged mapping assessment differs from audited source")
    mapping_attribution = json.loads(mapping_bytes)
    source_lock = json.loads((source / "source-lock.json").read_text("utf-8"))
    cpython_entries = [e for e in source_lock["archives"] if e.get("id") == "cpython"]
    if len(cpython_entries) != 1:
        raise ValueError("Exactly one pinned CPython source archive is required")
    gate = evaluate(
        {
            "mapping_attribution": mapping_attribution,
            "mapping_source_sha256": cpython_entries[0]["sha256"],
            "profile": profile,
            "source_clean": clean,
            "source_mode": source_status["mode"],
            "commit": revision,
            "manifest_sha256": digest(output / "manifest.json")["sha256"],
        },
        review_record,
    )
    return {
        "issue": 1398,
        "profile": profile,
        "integrity": "passed",
        **gate,
        "manifest": digest(output / "manifest.json"),
        "lock": digest(source / "package-lock.json"),
        "runtime_files": inventory["runtime_observations"]["runtime_files"],
        "components": inventory["components"],
        "source_delivery": {
            "Pyodide": source_status,
            "hiwire": source_status,
            "Core": "unmodified MIT sources and LICENSE inside core.zip; byte-verified",
            "stdlib": "567 source files mapped in source-provenance.json; full licence/attribution acceptance pending",
        },
        "inventory_review_notes": inventory["remaining_gates"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--require-publication",
        action="store_true",
        help="Require a complete approval claim in the record; human reference authentication in PUBLICATION_REVIEW.md is still mandatory",
    )
    parser.add_argument(
        "--review-record",
        type=Path,
        help="External final-head independent review and Owner decision record",
    )
    args = parser.parse_args()
    record = (
        json.loads(args.review_record.read_text("utf-8"))
        if args.review_record
        else None
    )
    report = audit(args.artifact, review_record=record)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_publication and not report["public_distribution_approved"]:
        parser.exit(
            1,
            "Publication blocked: attribution, corresponding source and independent review incomplete.\n",
        )


if __name__ == "__main__":
    main()
