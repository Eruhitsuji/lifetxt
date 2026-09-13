"""Evidence-first decision outcome projection."""

from collections import OrderedDict

_OUTCOME_BY_STATUS = {"[x]": "realized", "[-]": "canceled"}


def _ids(item, key):
    return {str(value) for value in item.details.get(key, [])}


def decision_outcome_review(items, id_key="id", limit=100):
    decisions = [
        item
        for item in items
        if item.kind == "N"
        and "decision" in {str(v) for v in item.details.get("tag", [])}
    ]
    rows = []
    for decision in decisions:
        dids = sorted(_ids(decision, id_key))
        did = dids[0] if dids else None
        evidence = []
        for item in items:
            realized = {str(value) for value in item.details.get("realizes", [])}
            if did and did in realized:
                evidence.append(
                    OrderedDict(
                        (
                            ("id", next(iter(_ids(item, id_key)), None)),
                            ("title", item.title),
                            ("status", item.status),
                            (
                                "outcome",
                                _OUTCOME_BY_STATUS.get(item.status, "observed"),
                            ),
                        )
                    )
                )
        outcomes = {row["outcome"] for row in evidence}
        outcome = next(
            (
                value
                for value in ("realized", "canceled", "observed")
                if value in outcomes
            ),
            "unresolved",
        )
        rows.append(
            OrderedDict(
                (
                    ("decision_id", did),
                    ("title", decision.title),
                    ("evidence", evidence[: int(limit)]),
                    ("outcome", outcome),
                )
            )
        )
    limitations = (
        []
        if all(row["evidence"] for row in rows)
        else ["only explicit realizes links are considered evidence"]
    )
    return OrderedDict(
        (
            ("schema", "decision-outcome-review-v1"),
            ("decisions", rows[: int(limit)]),
            ("limitations", limitations),
            ("complete", not bool(limitations)),
        )
    )
