"""Check isolated artifact integrity; incomplete attribution always blocks publication."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from contrib.browser_check_poc import build as builder
from contrib.browser_check_poc.notice_inventory import validate_notices


PINNED_LOCK_SHA256 = "03131c28d96b17f3d89d91e55b81ce29b4f57642d792f78b5f5195b44944d680"


def digest(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def audit(output, source=builder.SOURCE):
    """Return evidence, not legal clearance. Reject unlisted and changed bytes."""
    output = Path(output).resolve()
    source = Path(source)
    notices = validate_notices(source, output / "runtime")
    inventory = json.loads((source / "notices/components.json").read_text("utf-8"))
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
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

    source_status, source_files = audit_delivery(output, source)
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
        | source_files
    )
    files = list(output.rglob("*"))
    if any(f.is_symlink() for f in files):
        raise ValueError("Symlinks are not distribution assets")
    actual = {f.relative_to(output).as_posix() for f in files if f.is_file()}
    if actual != expected | {"manifest.json"} or set(manifest["files"]) != expected:
        raise ValueError("Artifact differs from fixed file allowlist")
    for name in sorted(expected):
        if digest(output / name) != manifest["files"][name]:
            raise ValueError("Artifact hash mismatch: " + name)
    for name, bound in inventory["runtime_observations"]["runtime_files"].items():
        if digest(output / name) != bound:
            raise ValueError("Runtime differs from audited binary: " + name)
    for name in notices:
        if digest(output / "notices" / name) != digest(source / "notices" / name):
            raise ValueError("Notice differs from reviewed source: " + name)
    for name in (
        "index.html",
        "ui.mjs",
        "worker.mjs",
        "engine.mjs",
        "adapter.py",
        "style.css",
    ):
        if digest(output / name) != digest(source / name):
            raise ValueError("Asset differs from build source: " + name)
    if manifest["core_modules"] != [
        f"lifetxt/{n}.py" for n in sorted(builder.CORE_MODULES)
    ]:
        raise ValueError("Core module allowlist mismatch")
    with zipfile.ZipFile(output / "core.zip") as archive:
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
    return {
        "issue": 1398,
        "integrity": "passed",
        "publication": "blocked",
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
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
        "blockers": inventory["remaining_gates"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--require-publication", action="store_true")
    args = parser.parse_args()
    report = audit(args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_publication:
        parser.exit(
            1,
            "Publication blocked: attribution, corresponding source and independent review incomplete.\n",
        )


if __name__ == "__main__":
    main()
