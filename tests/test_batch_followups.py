import unittest

from lifetxt.parser import parse_text
from lifetxt.historical_context import historical_personal_context
from lifetxt.decision_outcome_review import decision_outcome_review
from lifetxt.temporal_change_feed import temporal_change_feed


class BatchFollowupTests(unittest.TestCase):
    def test_historical_context_requires_cutoff_projection(self):
        items, _ = parse_text('[ ] N "Preference" person:self updated:2020-01-01\n')
        result = historical_personal_context(items, "2020-02-01T00:00:00+00:00")
        self.assertEqual("historical-personal-context-v1", result["schema"])

    def test_context_capsule_cutoff_is_explicit(self):
        from lifetxt.personal_context import context_capsule
        items, _ = parse_text('[ ] N "Preference" person:self updated:2020-01-01\n')
        self.assertEqual("personal-context-capsule-v1", context_capsule(items, evaluation_time="2020-02-01T00:00:00+00:00")["schema"])

    def test_decisions_and_feed_have_stable_schemas(self):
        items, _ = parse_text('[ ] N "Decision" tag:decision id:d1\n')
        self.assertEqual("decision-outcome-review-v1", decision_outcome_review(items)["schema"])
        self.assertEqual("temporal-change-feed-v1", temporal_change_feed(items, "2030-01-01T00:00:00+00:00")["schema"])
