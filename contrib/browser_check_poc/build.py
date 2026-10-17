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

VERSION = "314.0.7"
RUNTIME_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)


def build(output):
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
    package = json.loads((runtime / "package.json").read_text())
    if package["version"] != VERSION:
        raise ValueError("Install the exact pinned Pyodide using npm ci")
    fixtures = json.loads((SOURCE / "fixtures.json").read_text())
    expected = [{**f, "expected": check_text(f["text"])} for f in fixtures]
    # Explicit corpus-observed import closure. Never harvest ambient test-process
    # imports, which could accidentally bundle the CLI/Remote or unrelated modules.
    names = (
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
    modules = [ROOT / "lifetxt" / (name + ".py") for name in sorted(names)]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file in modules:
            name = file.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, file.read_bytes())
        license_info = zipfile.ZipInfo("LICENSE", (2026, 1, 1, 0, 0, 0))
        license_info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(license_info, (ROOT / "LICENSE").read_bytes())
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
    (output / "core.zip").write_bytes(archive.getvalue())
    (output / "fixtures.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2)
    )
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    manifest = {
        "pyodide": VERSION,
        "engine_base_revision": revision,
        "core_modules": [f.relative_to(ROOT).as_posix() for f in modules],
        "files": {
            f.relative_to(output).as_posix(): {
                "bytes": f.stat().st_size,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            }
            for f in sorted(output.rglob("*"))
            if f.is_file()
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "core_modules": len(modules),
                "core_zip_bytes": len(archive.getvalue()),
                "runtime_bytes": sum(
                    (runtime / n).stat().st_size for n in RUNTIME_FILES
                ),
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    build(p.parse_args().output)
