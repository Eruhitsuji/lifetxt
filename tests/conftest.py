"""Isolate the test session from the developer's own lifetxt setup.

Config discovery falls back to `.lifetxt.json` in the current directory, so a
real config sitting in the repository root silently becomes the config for
every test: `paths` overrides stdin input, `write_file` redirects writes, and
`ids.auto` changes generated output. That turned a green suite into 68
failures with no code change.

Tests address repository files through absolute paths and pass an explicit
`cwd` to any subprocess, so running the session from a clean temporary
directory removes the ambient config without changing what tests can reach. It
also keeps undo, backup, and session caches out of the working tree.
"""

import os
import shutil
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_working_directory():
    original = os.getcwd()
    sandbox = tempfile.mkdtemp(prefix="lifetxt-tests-")
    os.chdir(sandbox)
    try:
        yield sandbox
    finally:
        os.chdir(original)
        shutil.rmtree(sandbox, ignore_errors=True)
