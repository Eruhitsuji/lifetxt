#!/usr/bin/env python3
"""Classify changed paths for conservative CI routing."""

import argparse
from pathlib import Path


def classify(paths):
    normalized = [path.strip().lstrip("./") for path in paths if path.strip()]
    if not normalized:
        return "full"
    if all(path.startswith("docs/") for path in normalized):
        return "docs-only"

    def is_web(path):
        return path.startswith(("lifetxt/web", "tests/test_web")) or path == "requirements-web.txt"

    def is_tui(path):
        return path.startswith(("lifetxt/tui", "tests/test_tui", "tests/test_cui"))

    if all(path.startswith("docs/") or is_web(path) for path in normalized):
        return "web"
    if all(path.startswith("docs/") or is_tui(path) for path in normalized):
        return "tui"
    if any(is_web(path) for path in normalized) and any(is_tui(path) for path in normalized):
        return "full"
    if all(path.startswith(("docs/", "lifetxt/", "tests/", "scripts/", "examples/")) for path in normalized):
        return "python-core"
    return "full"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths_file")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    paths = Path(args.paths_file).read_text(encoding="utf-8").splitlines()
    category = classify(paths)
    output = f"category={category}\nrun-heavy={'false' if category == 'docs-only' else 'true'}\n"
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
