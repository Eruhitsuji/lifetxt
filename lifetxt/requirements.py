"""Parse and evaluate ID-based start conditions."""

from .model import VALID_STATUSES


STATES = dict(zip(
    ("not_started", "in_progress", "done", "canceled", "moved", "maybe", "note"),
    ("[ ]", "[/]", "[x]", "[-]", "[>]", "[?]", "[N]"),
))


def parse_requirement(value, depth=0):
    if depth > 32:
        raise ValueError("requires: supports up to 32 levels of conditions.")
    if isinstance(value, str):
        target, separator, states = value.rpartition("=")
        if separator:
            return _leaf(target, states.split(","))
    elif isinstance(value, dict):
        if set(value) == {"id", "state"}:
            state = value["state"]
            return _leaf(value["id"], state if isinstance(state, list) else [state])
        for operator in ("all", "any"):
            if set(value) == {operator} and isinstance(value[operator], list) and value[operator]:
                return operator, tuple(
                    parse_requirement(child, depth + 1) for child in value[operator]
                )
    raise ValueError("Use ID=state or a JSON object with id/state, all, or any.")


def _leaf(target, states):
    if not isinstance(target, str) or not target or any(c.isspace() for c in target):
        raise ValueError("requires: needs a nonempty ID without whitespace.")
    if not states or any(
        not isinstance(state, str) or (state not in STATES and state not in VALID_STATUSES)
        for state in states
    ):
        raise ValueError("requires: contains an unknown or empty state.")
    return "state", (target, tuple(STATES.get(state, state) for state in states))


def requirement_leaves(condition):
    operator, children = condition
    if operator == "state":
        yield children
    else:
        for child in children:
            yield from requirement_leaves(child)


def evaluate_requirement(condition, resolve):
    """Return (True, False, or None, unsuccessful leaf details)."""
    operator, children = condition
    if operator == "state":
        target_id, states = children
        target = resolve(target_id)
        result = None if target is None else target.status in states
        return result, [] if result else [(target_id, states, target)]

    outcome = [evaluate_requirement(child, resolve) for child in children]
    decisive = operator == "any"
    results = [result for result, _ in outcome]
    if decisive in results:
        result = decisive
    elif None in results:
        result = None
    else:
        result = not decisive
    return result, [] if result else [
        failure for _, failures in outcome for failure in failures
    ]
