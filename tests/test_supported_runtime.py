"""Refuse to certify the project on an interpreter it no longer supports.

`python -m unittest discover` happily runs on an interpreter below the declared
baseline. It does not report that it is doing so, and modules using newer syntax
simply fail to import -- the run finishes with a reduced test count and one
opaque error, which reads like a small bug rather than "these results mean
nothing". That is exactly the shape of misleading evidence the project's first
design principle warns about: fail loudly when behavior is ambiguous.

This module is deliberately written in old, widely-compatible syntax so it still
imports and reports on the very interpreters it exists to reject. Adding newer
syntax here would turn the clear message back into an import error.
"""

from __future__ import unicode_literals

import os
import re
import sys
import unittest


PYPROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml"
)

#: Matches the lower bound of `requires-python = ">=3.10"` and friends.
_REQUIRES_PYTHON = re.compile(
    r"""^\s*requires-python\s*=\s*["'][^"']*?>=\s*(\d+)\.(\d+)""", re.MULTILINE
)


class BaselineUnreadable(Exception):
    """Raised when the declared baseline cannot be determined.

    This is an error rather than a skip on purpose. A guard that silently passes
    when it cannot find the baseline is worse than no guard, because it still
    looks like proof.
    """


def declared_minimum(path=PYPROJECT_PATH):
    """Lowest interpreter version the project claims to support."""
    try:
        with open(path, "r") as handle:
            text = handle.read()
    except (IOError, OSError) as exc:
        raise BaselineUnreadable("Cannot read %s: %s" % (path, exc))
    match = _REQUIRES_PYTHON.search(text)
    if not match:
        raise BaselineUnreadable(
            'No `requires-python = ">=X.Y"` lower bound found in %s. The runtime '
            "guard cannot verify anything until that is restored." % path
        )
    return (int(match.group(1)), int(match.group(2)))


class SupportedRuntimeTests(unittest.TestCase):
    def test_declared_baseline_is_readable(self):
        """The guard must not be disarmed by a pyproject.toml reshuffle."""
        minimum = declared_minimum()
        self.assertEqual(2, len(minimum))
        self.assertGreaterEqual(minimum[0], 3)

    def test_running_interpreter_meets_the_declared_baseline(self):
        minimum = declared_minimum()
        running = sys.version_info[:2]
        self.assertGreaterEqual(
            running,
            minimum,
            "This suite is running on Python %d.%d, below the declared baseline of "
            "%d.%d in pyproject.toml. Results from an unsupported interpreter are "
            "not evidence: modules using newer syntax fail to import, so the run "
            "silently covers fewer tests than it appears to. Re-run on Python "
            "%d.%d or newer before recording any result."
            % (running[0], running[1], minimum[0], minimum[1], minimum[0], minimum[1]),
        )


if __name__ == "__main__":
    unittest.main()
