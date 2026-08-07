"""The replace-retry policy is duplicated on purpose, so pin the copies together.

`lifetxt/atomic.py` and `lifetxt/transaction_journal.py` each define their own
`_REPLACE_PERMISSION_RETRY_*` constants and their own retry loop. That is a
recorded decision, not an oversight: sharing the code would have meant editing
`transaction_journal.py`, which is incident-hardened and fault-injection-tested,
and which the `windows-atomic-replace-retry` change package placed in forbidden
scope. See that package's `decisions.md`.

The cost of that decision is drift. `design.md` recorded it as the residual risk
and proposed this test as the mitigation -- and then the mitigation was never
written, so `req-atomic-replace-retry-policy-consistency` had no test behind it
until #116. Closing out the package found the traceability entry claiming
assertions that did not exist.

These assert equality, never the values themselves. Changing the policy on
purpose stays a two-line edit; changing it in one place only fails here.
"""

from __future__ import unicode_literals

import unittest

from lifetxt import atomic, transaction_journal


DELIBERATE = (
    "The duplication is deliberate: transaction_journal.py keeps its own retry "
    "implementation because sharing it would edit incident-hardened, "
    "fault-injection-tested code, which the windows-atomic-replace-retry change "
    "package placed in forbidden scope. Do not resolve this failure by deleting "
    "one copy. Either change both, or revisit that decision in a new change "
    "package. See .ai/project/changes/windows-atomic-replace-retry/decisions.md."
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
