"""Read-only runtime build identity for Web UI test evidence.

Git HEAD is captured at Web app startup, anchored to the imported package's
source checkout. It is not a guarantee that a working tree is clean or that
every currently loaded Python module matches that commit.
"""

from pathlib import Path
import re
import subprocess

from . import __version__


_GIT_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def git_head_for_checkout(source_root: Path) -> str | None:
    """Return a verified Git HEAD only for the imported package checkout."""
    if not (source_root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(source_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=2,
            check=False,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return None
    commit = result.stdout.strip()
    if result.returncode != 0 or not _GIT_SHA.fullmatch(commit):
        return None
    return commit


def snapshot_runtime_build_info() -> dict[str, str | None]:
    """Snapshot version and source HEAD once while the Web app starts."""
    source_root = Path(__file__).resolve().parent.parent
    return {
        "version": __version__,
        "git_commit": git_head_for_checkout(source_root),
    }
