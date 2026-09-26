import unittest
from datetime import datetime

from lifetxt.model import Item
from lifetxt.personal_context_currentness import (
    STATE_CONFLICTING,
    STATE_CURRENT,
    STATE_EXPIRED,
    STATE_FUTURE_EFFECTIVE,
    STATE_HISTORICAL_ONLY,
    STATE_STALE,
    STATE_SUPERSEDED,
    parse_validity_bounds,
    resolve_currentness,
)


def _note(id_value, **details):
    merged = {"id": [id_value]}
    for key, value in details.items():
        merged[key] = value if isinstance(value, list) else [value]
    return Item(status="[ ]", kind="N", title="note %s" % id_value, details=merged)


class ParseValidityBoundsTests(unittest.TestCase):
    def test_no_bounds_present(self):
        valid_from, valid_to, malformed = parse_validity_bounds(_note("a"))
        self.assertIsNone(valid_from)
        self.assertIsNone(valid_to)
        self.assertFalse(malformed)

    def test_valid_from_only(self):
        valid_from, valid_to, malformed = parse_validity_bounds(
            _note("a", valid_from="2026-01-01")
        )
        self.assertIsNotNone(valid_from)
        self.assertIsNone(valid_to)
        self.assertFalse(malformed)

    def test_valid_to_only(self):
        valid_from, valid_to, malformed = parse_validity_bounds(
            _note("a", valid_to="2026-01-01")
        )
        self.assertIsNone(valid_from)
        self.assertIsNotNone(valid_to)
        self.assertFalse(malformed)

    def test_both_bounds(self):
        valid_from, valid_to, malformed = parse_validity_bounds(
            _note("a", valid_from="2026-01-01", valid_to="2026-02-01")
        )
        self.assertIsNotNone(valid_from)
        self.assertIsNotNone(valid_to)
        self.assertFalse(malformed)

    def test_malformed_value(self):
        _, _, malformed = parse_validity_bounds(_note("a", valid_from="not-a-date"))
        self.assertTrue(malformed)

    def test_reversed_range_is_malformed(self):
        _, _, malformed = parse_validity_bounds(
            _note("a", valid_from="2026-02-01", valid_to="2026-01-01")
        )
        self.assertTrue(malformed)


class ResolveCurrentnessTests(unittest.TestCase):
    def test_review_policy_only_controls_age_transition(self):
        old = _note("old", updated="2000-01-01", review="never")
        state = resolve_currentness([old])["old"]
        self.assertEqual(STATE_CURRENT, state["state"])
        self.assertFalse(state["review_due"])
        self.assertIsNotNone(state["raw_stale_fact"])
        self.assertEqual("record_override", state["review_policy"]["source"])
        old.details["valid_to"] = ["2001-01-01"]
        self.assertEqual(STATE_EXPIRED, resolve_currentness([old])["old"]["state"])
        historical = resolve_currentness([old], apply_review_policy=False)["old"]
        self.assertEqual(STATE_EXPIRED, historical["state"])
        del old.details["valid_to"]
        self.assertEqual(STATE_STALE, resolve_currentness(
            [old], apply_review_policy=False,
        )["old"]["state"])

    def test_invalid_override_falls_back_and_tag_policies_are_order_independent(self):
        old = _note("old", updated="2000-01-01", review="unknown",
                    tag=["never_tag", "short_tag", "long_tag"])
        policies = {"never_tag": {"mode": "never"},
                    "long_tag": {"mode": "periodic", "days": 365},
                    "short_tag": {"mode": "periodic", "days": 10}}
        result = resolve_currentness([old], tag_policies=policies)["old"]
        self.assertEqual(STATE_STALE, result["state"])
        self.assertEqual(10, result["review_policy"]["days"])
        self.assertIn("invalid_record_review_policy", result["review_policy"]["diagnostics"])
        old.details["tag"] = list(reversed(old.details["tag"]))
        reordered = resolve_currentness([old], tag_policies=policies)["old"]
        self.assertEqual(result["state"], reordered["state"])
        self.assertEqual(result["review_policy"], reordered["review_policy"])

    def test_plain_item_is_current(self):
        items = [_note("a")]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_CURRENT)

    def test_future_effective(self):
        items = [_note("a", valid_from="2999-01-01")]
        states = resolve_currentness(items, evaluation_time=datetime(2026, 1, 1))
        self.assertEqual(states["a"]["state"], STATE_FUTURE_EFFECTIVE)

    def test_expired(self):
        items = [_note("a", valid_to="2000-01-01")]
        states = resolve_currentness(items, evaluation_time=datetime(2026, 1, 1))
        self.assertEqual(states["a"]["state"], STATE_EXPIRED)

    def test_bounded_interval_current_inside_window(self):
        items = [_note("a", valid_from="2026-01-01", valid_to="2026-12-31")]
        states = resolve_currentness(items, evaluation_time=datetime(2026, 6, 1))
        self.assertEqual(states["a"]["state"], STATE_CURRENT)

    def test_malformed_never_resolves_to_current(self):
        items = [_note("a", valid_from="garbage")]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_CONFLICTING)

    def test_reversed_range_never_resolves_to_current(self):
        items = [_note("a", valid_from="2026-02-01", valid_to="2026-01-01")]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_CONFLICTING)

    def test_explicit_historical_only(self):
        items = [_note("a")]
        states = resolve_currentness(items, historical_ids={"a"})
        self.assertEqual(states["a"]["state"], STATE_HISTORICAL_ONLY)

    def test_stale_via_node_facts(self):
        items = [_note("a", updated="2000-01-01T00:00:00")]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_STALE)

    def test_item_without_id_is_still_classified(self):
        item = Item(status="[ ]", kind="N", title="no id", details={})
        item.source = "life.txt"
        item.line = 5
        states = resolve_currentness([item])
        record = list(states.values())[0]
        self.assertEqual(record["state"], STATE_CURRENT)
        self.assertIsNone(record["id"])

    def test_linear_chain_predecessor_superseded_terminal_current(self):
        items = [
            _note("a", replaced_by="b"),
            _note("b"),
        ]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_SUPERSEDED)
        self.assertEqual(states["b"]["state"], STATE_CURRENT)

    def test_corrects_convention_supersedes_target(self):
        items = [
            _note("old"),
            _note("new", corrects="old"),
        ]
        states = resolve_currentness(items)
        self.assertEqual(states["old"]["state"], STATE_SUPERSEDED)
        self.assertEqual(states["new"]["state"], STATE_CURRENT)

    def test_competing_replacements_are_conflicting(self):
        items = [
            _note("old"),
            _note("new1", corrects="old"),
            _note("new2", corrects="old"),
        ]
        states = resolve_currentness(items)
        self.assertEqual(states["old"]["state"], STATE_CONFLICTING)
        self.assertEqual(states["new1"]["state"], STATE_CONFLICTING)
        self.assertEqual(states["new2"]["state"], STATE_CONFLICTING)

    def test_cycle_is_conflicting(self):
        items = [
            _note("a", replaced_by="b"),
            _note("b", replaced_by="a"),
        ]
        states = resolve_currentness(items)
        self.assertEqual(states["a"]["state"], STATE_CONFLICTING)
        self.assertEqual(states["b"]["state"], STATE_CONFLICTING)

    def test_deterministic_reasons_present(self):
        items = [_note("a", replaced_by="b"), _note("b")]
        states = resolve_currentness(items)
        self.assertTrue(states["a"]["reasons"])


if __name__ == "__main__":
    unittest.main()
