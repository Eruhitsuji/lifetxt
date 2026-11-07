"""Create the standalone Node.js checker ZIP and its SHA-256."""

import argparse
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    archive = output / "lifetxt-js-check.zip"
    paths = [source / name for name in ("README.md", "check.mjs", "parser.mjs")]
    paths.append(source.parents[1] / "LICENSE")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zip_file:
        for path in paths:
            zip_file.writestr(ZipInfo(path.name), path.read_bytes(), ZIP_DEFLATED)
    checksum = sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {archive.name}\n", encoding="ascii"
    )


if __name__ == "__main__":
    main()
