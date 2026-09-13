"""Evidence-first decision outcome projection."""

from collections import OrderedDict


def decision_outcome_review(items, id_key="id", limit=100):
    decisions = [item for item in items if item.kind == "N" and "decision" in [str(v) for v in item.details.get("tag", [])]]
    evidence = [item for item in items if item.kind in ("T", "N", "J")]
    rows = []
    for decision in decisions:
        dids = [str(v) for v in decision.details.get(id_key, [])]
        rows.append(OrderedDict((("decision_id", dids[0] if dids else None), ("title", decision.title), ("evidence", []), ("outcome", "unresolved"))))
    return OrderedDict((("schema", "decision-outcome-review-v1"), ("decisions", rows[:int(limit)]), ("limitations", ["evidence requires explicit links or references"] if evidence else [])))
