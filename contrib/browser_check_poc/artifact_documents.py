"""Pin copied documentation links to the actual build commit without self-reference."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PREFIX = b"https://github.com/Eruhitsuji/lifetxt/blob/"


def revision():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def document_bytes(path):
    return path.read_bytes().replace(
        PREFIX + b"main/", PREFIX + revision().encode("ascii") + b"/"
    )
