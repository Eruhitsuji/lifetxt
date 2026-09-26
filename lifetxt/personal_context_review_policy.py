"""Effective, workspace-defined Personal Context review policy.

Policies affect only periodic freshness review, never validity or history.
"""

from __future__ import unicode_literals


def effective_review_policy(item, stale_after_days, tag_policies=None):
    """Resolve record override, matching tags, then the global fallback.

    Invalid inputs produce diagnostics and retain periodic review. A malformed
    record override does not grant an exemption or mask valid tag policies.
    """
    result = {
        "mode": "periodic",
        "days": int(stale_after_days),
        "source": "global_fallback",
        "diagnostics": [],
    }
    policies = tag_policies or {}
    if not isinstance(policies, dict):
        result["diagnostics"].append("invalid_tag_policies")
        policies = {}
    candidates = []
    for tag in sorted(set(str(v) for v in item.details.get("tag", []))):
        if tag not in policies:
            continue
        policy = policies[tag]
        if not isinstance(policy, dict) or policy.get("mode") not in (
            "periodic",
            "never",
        ):
            result["diagnostics"].append("invalid_tag_policy:%s" % tag)
            continue
        if policy["mode"] == "periodic":
            days = policy.get("days")
            if isinstance(days, bool) or not isinstance(days, int) or days < 0:
                result["diagnostics"].append("invalid_tag_policy:%s" % tag)
                continue
            candidates.append((0, days, tag, "periodic"))
        else:
            candidates.append((1, 0, tag, "never"))
    if candidates:
        _, days, tag, mode = min(candidates)
        result.update(
            mode=mode, days=days if mode == "periodic" else None, source="tag:%s" % tag
        )
    override = [str(v) for v in item.details.get("review", [])]
    if override:
        if override == ["never"]:
            result.update(mode="never", days=None, source="record_override")
        else:
            result["diagnostics"].append("invalid_record_review_policy")
    return result


def configured_tag_policies(config):
    """Read optional review configuration without assigning tag semantics."""
    section = (config or {}).get("personal_context") or {}
    review = section.get("review") or {} if isinstance(section, dict) else {}
    return review.get("tag_policies") or {} if isinstance(review, dict) else {}
