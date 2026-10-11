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
        return (
            path.startswith(("lifetxt/web", "tests/test_web"))
            or path == "requirements-web.txt"
        )

    def is_tui(path):
        return path.startswith(("lifetxt/tui", "tests/test_tui", "tests/test_cui"))

    if all(path.startswith("docs/") or is_web(path) for path in normalized):
        return "web"
    if all(path.startswith("docs/") or is_tui(path) for path in normalized):
        return "tui"
    if any(is_web(path) for path in normalized) and any(
        is_tui(path) for path in normalized
    ):
        return "full"
    if all(
        path.startswith(("docs/", "lifetxt/", "tests/", "scripts/", "examples/"))
        for path in normalized
    ):
        return "python-core"
    return "full"


def compatibility_checks(paths, added_paths=()):
    """Select PR checks, including coverage for newly added product modules."""
    normalized = [path.strip().removeprefix("./") for path in paths if path.strip()]
    added = [path.strip().removeprefix("./") for path in added_paths if path.strip()]
    coverage = not normalized or any(
        path in {"pyproject.toml", "setup.cfg", "setup.py", ".coveragerc"}
        or path.startswith(
            (
                ".github/workflows/",
                "requirements",
                "scripts/check_coverage",
                "scripts/coverage-",
                "tests/test_coverage",
            )
        )
        for path in normalized
    )
    # New product modules may lower branch coverage even when other PR checks pass.
    # Preserve the existing selection behavior for edits to existing modules.
    coverage = coverage or any(
        path.startswith("lifetxt/") and path.endswith(".py") for path in added
    )
    no_web = coverage or any(
        path.startswith(("tests/", "lifetxt/", "scripts/")) for path in normalized
    )
    return no_web, coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths_file")
    parser.add_argument("--github-output")
    parser.add_argument("--added-paths-file", type=Path)
    args = parser.parse_args()
    paths = Path(args.paths_file).read_text(encoding="utf-8").splitlines()
    category = classify(paths)
    added_paths = (
        args.added_paths_file.read_text(encoding="utf-8").splitlines()
        if args.added_paths_file is not None
        else ()
    )
    no_web, coverage = compatibility_checks(paths, added_paths=added_paths)
    output = f"category={category}\nrun-heavy={'false' if category == 'docs-only' else 'true'}\n"
    output += (
        f"run-no-web={str(no_web).lower()}\nrun-coverage={str(coverage).lower()}\n"
    )
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
