"""Build isolated, self-hosted PoC; no production website or Core edits (#1356)."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from contrib.browser_check_poc.adapter import check_text
from contrib.browser_check_poc.artifact_documents import document_bytes
from contrib.browser_check_poc.notice_inventory import (
    validate_notices,
    write_notice_index,
)

VERSION = "314.0.7"
RUNTIME_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)


CORE_MODULES = (
    "__init__",
    "atomic",
    "config",
    "diagnostic_contract",
    "ids",
    "links",
    "model",
    "mutation",
    "parser",
    "progress",
    "recurrence",
    "safety_foundation",
    "serializer",
    "temporal_context",
    "temporal_thread",
    "ticket_project_values",
    "tickets",
    "timeutil",
    "timezone_policy",
    "validator",
)


def core_archive_bytes():
    """Canonical ZIP bytes, independent of host platform and zlib version."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
        for name in [f"lifetxt/{n}.py" for n in sorted(CORE_MODULES)] + ["LICENSE"]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, (ROOT / name).read_bytes())
    return archive.getvalue()


def build(output, source_cache=None):
    output = output.resolve()
    if (
        output == ROOT
        or output.is_relative_to(SOURCE)
        or output.is_relative_to(ROOT / "lifetxt")
        or output.is_relative_to(ROOT / "website")
        or output.is_relative_to(ROOT / ".ai")
    ):
        raise ValueError("output must be separate from repository sources")
    runtime = SOURCE / "node_modules/pyodide"
    package = json.loads((runtime / "package.json").read_text(encoding="utf-8"))
    if package["version"] != VERSION:
        raise ValueError("Install the exact pinned Pyodide using npm ci")
    notice_files = validate_notices(SOURCE, runtime)
    fixtures = json.loads((SOURCE / "fixtures.json").read_text(encoding="utf-8"))
    expected = [{**f, "expected": check_text(f["text"])} for f in fixtures]
    # Explicit corpus-observed import closure. Never harvest ambient test-process
    # imports, which could accidentally bundle the CLI/Remote or unrelated modules.
    modules = [ROOT / "lifetxt" / (name + ".py") for name in sorted(CORE_MODULES)]
    archive = core_archive_bytes()
    from contrib.browser_check_poc.source_delivery import (
        load_lock,
        validate_cache,
        write_delivery,
    )

    if source_cache is not None:
        validate_cache(Path(source_cache), load_lock(SOURCE))
    output.mkdir(parents=True, exist_ok=False)
    (output / "runtime").mkdir()
    for name in RUNTIME_FILES:
        shutil.copyfile(runtime / name, output / "runtime" / name)
    for name in (
        "index.html",
        "ui.mjs",
        "worker.mjs",
        "engine.mjs",
        "adapter.py",
        "style.css",
    ):
        shutil.copyfile(SOURCE / name, output / name)
    (output / "notices").mkdir()
    for name in notice_files:
        if name == "README.md":
            (output / "notices" / name).write_bytes(
                document_bytes(SOURCE / "notices" / name)
            )
        else:
            shutil.copyfile(SOURCE / "notices" / name, output / "notices" / name)
    write_notice_index(output / "notices", SOURCE)
    (output / "core.zip").write_bytes(archive)
    (output / "fixtures.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    write_delivery(output / "sources", SOURCE, source_cache)
    write_manifest(output, [f.relative_to(ROOT).as_posix() for f in modules])
    from contrib.browser_check_poc.distribution_audit import audit

    audit(output, SOURCE)
    print(
        json.dumps(
            {
                "core_modules": len(modules),
                "core_zip_bytes": len(archive),
                "runtime_bytes": sum(
                    (runtime / n).stat().st_size for n in RUNTIME_FILES
                ),
            }
        )
    )


def write_manifest(output, core_modules, profile="poc"):
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    manifest = {
        "pyodide": VERSION,
        "engine_base_revision": revision,
        "core_modules": core_modules,
        "profile": profile,
        "files": {
            f.relative_to(output).as_posix(): {
                "bytes": f.stat().st_size,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            }
            for f in sorted(
                output.rglob("*"), key=lambda p: p.relative_to(output).as_posix()
            )
            if f.is_file()
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--source-cache",
        type=Path,
        help="Offline verified source archives to self-host",
    )
    args = p.parse_args()
    build(args.output, args.source_cache)
