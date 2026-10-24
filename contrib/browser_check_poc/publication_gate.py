"""Evaluate review evidence; this command neither approves nor deploys anything."""

import re

P1 = {f"P1-{n}" for n in range(1, 5)}
P2 = {f"P2-{n}" for n in range(5, 9)}


def evaluate(facts, record=None):
    """Record is external to the artifact so final-head review cannot be circular.

    Human reviewers authenticate its authors/references outside this offline tool.
    A fabricated record is not authority. The tool checks completeness/freshness.
    """
    blockers = []
    record = {} if record is None else record
    if not isinstance(record, dict) or not isinstance(facts, dict):
        raise ValueError("Publication evidence must be JSON objects")
    for key in ("findings", "source_retention", "publication_approval"):
        if key in record and not isinstance(record[key], dict):
            raise ValueError("Invalid publication evidence object: " + key)
    if "reviews" in record and not isinstance(record["reviews"], list):
        raise ValueError("Reviews must be a list")
    if not facts.get("source_clean"):
        blockers.append(
            "Reviewed source checkout is modified or contains untracked build inputs"
        )
    if not record.get("implementer"):
        blockers.append("Implementer identity is missing")
    if facts.get("source_mode") != "hash-verified-self-hosted-archives":
        blockers.append(
            "Publication requires all ten verified same-origin source archives"
        )
    if facts.get("profile") != "website-checker":
        blockers.append("Publication requires the final website-checker artifact")
    if record.get("schema_version") != 1:
        blockers.append("Missing versioned independent distribution acceptance record")
    commit = facts.get("commit", "")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", commit)
        or record.get("target_commit") != commit
    ):
        blockers.append("Review is absent or stale for the final source commit")
    if not re.fullmatch(
        r"[0-9a-f]{64}", facts.get("manifest_sha256", "")
    ) or record.get("manifest_sha256") != facts.get("manifest_sha256"):
        blockers.append("Review does not bind this final artifact manifest")
    findings = record.get("findings", {})
    if set(findings) != P1 | P2:
        blockers.append("All P1/P2 findings require explicit dispositions")
    for finding in sorted(P1 | P2):
        entry = findings.get(finding, {})
        if not isinstance(entry, dict):
            raise ValueError("Finding disposition must be an object")
        allowed = {"fixed"} if finding in P1 else {"fixed", "owner-risk-accepted"}
        if entry.get("status") not in allowed or not entry.get("evidence"):
            blockers.append(finding + " lacks an evidenced disposition")
        if finding in {"P2-6", "P2-7"} or entry.get("status") == "owner-risk-accepted":
            if not entry.get("verified_scope") or not entry.get("remaining_risk"):
                blockers.append(
                    finding + " must distinguish verified scope and remaining risk"
                )
            if entry.get("owner") != "Eruhitsuji":
                blockers.append(finding + " requires recorded Owner judgment")
    retention = record.get("source_retention", {})
    if (
        retention.get("owner") != "Eruhitsuji"
        or retention.get("minimum_period") != "entire-binary-distribution-period"
        or not retention.get("reference")
    ):
        blockers.append("Owner same-origin source retention commitment is missing")
    reviews = record.get("reviews", [])
    for viewpoint in ("implementation-distribution", "integration"):
        if not any(
            r.get("type") == viewpoint
            and r.get("result") == "accepted"
            and r.get("reviewer")
            and r.get("reviewer") != record.get("implementer")
            and r.get("target_commit") == commit
            and r.get("reference")
            for r in reviews
            if isinstance(r, dict)
        ):
            blockers.append("Missing independent final-head " + viewpoint + " review")
    complete = not blockers
    approval = record.get("publication_approval", {})
    approved = (
        complete
        and approval.get("owner") == "Eruhitsuji"
        and approval.get("target_commit") == commit
        and approval.get("manifest_sha256") == facts.get("manifest_sha256")
        and approval.get("decision") == "approved"
        and bool(approval.get("reference"))
    )
    if not approved:
        blockers.append(
            "Separate explicit Owner publication approval is absent or stale"
        )
    return {
        "publication": "eligible-for-owner-deployment" if approved else "blocked",
        "complete_distribution_audit": complete,
        "public_distribution_approved": approved,
        "blockers": blockers,
    }
