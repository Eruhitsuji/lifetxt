"""PyInstaller entry-point script.

PyInstaller's Analysis step needs a runnable script, not a module reference,
so this thin launcher exists only to call the same entry point
`pyproject.toml`'s `[project.scripts]` console entry already uses
(`lifetxt.entrypoint:main`). No application logic is duplicated here.
"""

from lifetxt.entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())
