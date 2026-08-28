#!/usr/bin/env python
"""Generate the conda-forge recipe (meta.yaml) for one lifetxt release.

conda-forge's `staged-recipes` submission builds from the PyPI sdist (#568)
rather than a second, independent source archive -- this recipe is a thin
adapter, matching every other package-manager integration in this project.
It cannot be generated until a real PyPI release exists to compute the
sdist's checksum from (see docs/en/distribution.md#6-conda-forge for the
one-time submission steps this script does not perform).

Usage:
    python scripts/generate_conda_recipe.py \\
        --version 1.0.0 \\
        --sha256 <sha256 of the lifetxt-1.0.0.tar.gz sdist published to PyPI> \\
        --output-dir packaging/conda-forge/generated/recipe
"""

from __future__ import print_function

import argparse
import re
import sys
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def build_meta_yaml(version, sha256):
    if not _SHA256_RE.match(sha256):
        raise ValueError("--sha256 must be a 64-character hex SHA-256 digest")
    return """{{% set name = "lifetxt" %}}
{{% set version = "{version}" %}}

package:
  name: {{{{ name|lower }}}}
  version: {{{{ version }}}}

source:
  url: https://pypi.io/packages/source/{{{{ name[0] }}}}/{{{{ name }}}}/lifetxt-{{{{ version }}}}.tar.gz
  sha256: {sha256}

build:
  number: 0
  noarch: python
  script: {{{{ PYTHON }}}} -m pip install . -vv --no-deps --no-build-isolation
  entry_points:
    - lifetxt = lifetxt.entrypoint:main

requirements:
  host:
    - python >=3.10
    - pip
    - setuptools >=61
  run:
    - python >=3.10
    - tzdata  # [win]

test:
  imports:
    - lifetxt
  commands:
    - lifetxt --version
    - lifetxt check --help
  requires:
    - pip

about:
  home: https://github.com/Eruhitsuji/lifetxt
  summary: Parser, validator, converter, CLI, and optional web UI for life.txt.
  license: MIT
  license_file: LICENSE
  doc_url: https://github.com/Eruhitsuji/lifetxt/tree/main/docs/en
  dev_url: https://github.com/Eruhitsuji/lifetxt

extra:
  recipe-maintainers:
    - Eruhitsuji
""".format(version=version, sha256=sha256.lower())


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.0.0")
    parser.add_argument(
        "--sha256",
        required=True,
        help="SHA-256 of the published PyPI sdist (lifetxt-<version>.tar.gz)",
    )
    parser.add_argument(
        "--output-dir",
        default="packaging/conda-forge/generated/recipe",
        help="Directory to write meta.yaml into",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        content = build_meta_yaml(args.version, args.sha256)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "meta.yaml"
    output_path.write_text(content, encoding="utf-8", newline="\n")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
