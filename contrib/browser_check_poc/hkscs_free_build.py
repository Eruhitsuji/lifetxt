"""Single-write build outputs for the pinned custom Pyodide profile (#1415)."""

import argparse
import importlib.util
import io
import os
from pathlib import Path
import re
import zipfile


def embed(root):
    core = root / "src/core"
    body = (
        b"()<::>{\n"
        + (root / "src/js/generated/_pyodide.out.js").read_bytes()
        + b"}\n"
        + (core / "stack_switching/stack_switching.out.js").read_bytes()
        + (core / "pre.js").read_bytes()
        + b"pyodide_js_init();\n"
    )
    (core / "pyodide_pre.gen.dat").write_bytes(body)


def stdlib(libdirs, excludes, stubs, output, compression_level):
    # Reuse the pinned upstream selection rules, including JS stub exclusions.
    spec = importlib.util.spec_from_file_location(
        "upstream_zip", Path("tools/create_zipfile.py")
    )
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    files = {}
    for root in libdirs:
        ignore = upstream.default_filterfunc(root, excludes, stubs)
        for directory, dirs, names in os.walk(root):
            base = Path(directory)
            skipped = ignore(base, dirs + names)
            dirs[:] = sorted(x for x in dirs if x not in skipped)
            for name in sorted(names):
                if name not in skipped:
                    path = base / name
                    files[path.relative_to(root).as_posix()] = path.read_bytes()
    compression = zipfile.ZIP_DEFLATED if compression_level else zipfile.ZIP_STORED
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=compression, compresslevel=compression_level
    ) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = compression
            archive.writestr(info, data, compresslevel=compression_level)
    data = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if (
            archive.testzip() is not None
            or "encodings/__init__.py" not in archive.namelist()
        ):
            raise ValueError("invalid generated stdlib")
    output.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("embed", "stdlib"))
    parser.add_argument("libdirs", nargs="*", type=Path)
    parser.add_argument("--exclude", default="")
    parser.add_argument("--stub", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compression-level", type=int, default=6)
    args = parser.parse_args()
    if args.mode == "embed":
        embed(Path.cwd())
    else:
        if not args.libdirs or args.output is None:
            parser.error("stdlib requires input directories and --output")
        stdlib(
            args.libdirs,
            re.split(r"[,\s]+", args.exclude.strip()),
            re.split(r"[,\s]+", args.stub.strip()),
            args.output,
            args.compression_level,
        )


if __name__ == "__main__":
    main()
