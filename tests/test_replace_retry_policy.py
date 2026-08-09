"""The replace-retry policy constants are shared; the retry loop is not.

`lifetxt/atomic.py` originally defined its own `_REPLACE_PERMISSION_RETRY_*`
constants independently of `lifetxt/transaction_journal.py`'s copy -- a
recorded decision at the time (`windows-atomic-replace-retry`'s
`decisions.md`), because sharing the *retry loop* would have meant editing
`transaction_journal.py`, which is incident-hardened and fault-injection-
tested, and which that change package placed in forbidden scope. That same
`decisions.md` entry noted "a future spec could migrate transaction_journal.py
onto the shared helper."

The `replace-retry-policy-dedup` change did exactly that, but only for the two
constants: `transaction_journal.py` now imports them from `atomic.py` instead
of defining its own copy, so the values cannot drift by construction. The
retry *loop* in `transaction_journal._replace_file` still exists separately,
because it interleaves a `fault_point()` hook per attempt for the
crash-recovery test matrix (`tests/test_transaction_journal_v3.py`), which
`atomic.replace_with_retry` does not provide and should not grow just to
serve this one caller.

These tests keep asserting equality (now structurally guaranteed by the
import) plus the bounded-budget property, rather than being deleted: they
remain the regression guard if a future edit reintroduces a second literal
definition instead of importing the shared one.
"""

from __future__ import unicode_literals

import unittest

from lifetxt import atomic, transaction_journal


DELIBERATE = (
    "atomic.py and transaction_journal.py must reference the identical "
    "_REPLACE_PERMISSION_RETRY_* constants (transaction_journal.py imports "
    "them from atomic.py; see the replace-retry-policy-dedup change). If this "
    "fails, a second literal definition was reintroduced somewhere -- fix it "
    "by importing the shared constants, not by hand-syncing two copies."
)


class ReplaceRetryPolicyConsistencyTests(unittest.TestCase):
    """Evidence for `req-atomic-replace-retry-policy-consistency`."""

    def test_retry_platforms_match(self):
        self.assertEqual(
            atomic._REPLACE_PERMISSION_RETRY_OS_NAMES,
            transaction_journal._REPLACE_PERMISSION_RETRY_OS_NAMES,
            "atomic and transaction_journal disagree about which platforms retry. "
            + DELIBERATE,
        )

    def test_retry_delays_match(self):
        self.assertEqual(
            atomic._REPLACE_PERMISSION_RETRY_DELAYS_SECONDS,
            transaction_journal._REPLACE_PERMISSION_RETRY_DELAYS_SECONDS,
            "atomic and transaction_journal disagree about the retry delays. "
            + DELIBERATE,
        )

    def test_both_copies_describe_a_bounded_budget(self):
        """A policy with no bound would make a stuck handle hang a write forever.

        This is the one property asserted about the values rather than about
        their equality, because an unbounded budget would be wrong in either
        module regardless of whether they agree.
        """
        for module in (atomic, transaction_journal):
            delays = module._REPLACE_PERMISSION_RETRY_DELAYS_SECONDS
            self.assertIsInstance(delays, tuple, module.__name__)
            self.assertTrue(delays, "%s has an empty retry budget" % module.__name__)
            self.assertTrue(
                all(delay >= 0 for delay in delays),
                "%s has a negative retry delay" % module.__name__,
            )
            self.assertLess(
                sum(delays),
                5.0,
                "%s would wait %.2fs before giving up; a write should not stall that long "
                "on a transient handle" % (module.__name__, sum(delays)),
            )


if __name__ == "__main__":
    unittest.main()
