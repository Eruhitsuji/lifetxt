"""Check record shape/binding only; never authenticate an author or grant authority."""

import re
from urllib.parse import urlsplit

P1 = {f"P1-{n}" for n in range(1, 5)}
P2 = {f"P2-{n}" for n in range(5, 9)}
NEW_P2 = {"N-1", "N-2", "N-3", "N-7"}
# Current task's implementing AI tools, anchored outside the reviewer's record.
IMPLEMENTER_TOOLS = frozenset({"codex"})
OWNER = "eruhitsuji"


def login(value):
    return (
        value.casefold()
        if isinstance(value, str)
        and re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,38})", value)
        else None
    )


def tool(value):
    if not isinstance(value, str):
        return None
    value = value.strip().casefold()
    return {"claude": "claude-code", "claude code": "claude-code"}.get(value, value)


def reference(value):
    """Only repository discussion URLs, not arbitrary truthy evidence strings.

    This checks syntax, NOT existence, authorship or decision content.
    """
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return bool(
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and not parsed.query
        and re.fullmatch(
            r"/Eruhitsuji/lifetxt/(?:issues|pull)/[1-9][0-9]*", parsed.path
        )
        and re.fullmatch(
            r"(?:issuecomment-|pullrequestreview-|discussion_r)[1-9][0-9]*",
            parsed.fragment,
        )
    )


# Known permission blockers cannot be turned into non-blocking "pending" rows.
MAPPING_REQUIRED_IDS = frozenset({
    "ucd-16-and-3.2", "unicode-mappings", "hkscs-2004",
    "icu-gb18030", "jis-x-0213", "gb2312",
})
MAPPING_PERMISSION_BLOCKERS = frozenset({"hkscs-2004", "icu-gb18030"})
MAPPING_PENDING = frozenset({
    "independent-acceptance-pending",
    "notice-retained-independent-acceptance-pending",
})
MAPPING_RESOLVED = frozenset({
    "resolved-removed", "resolved-terms-confirmed", "resolved-owner-judgment",
})


def mapping_blockers(mapping, pinned_source_sha):
    """Reject unresolved mapping licences regardless of Owner-risk claims.

    This validates the shape and source binding of evidence, not legal validity.
    PUBLICATION_REVIEW.md still requires human verification of every reference.
    """
    if not isinstance(mapping, dict) or mapping.get("schema_version") != 1:
        return ["Missing or invalid mapping-attribution data"]
    if (
        not isinstance(pinned_source_sha, str)
        or not re.fullmatch(r"[0-9a-f]{64}", pinned_source_sha)
        or mapping.get("source_archive_sha256") != pinned_source_sha
    ):
        return ["Mapping attribution is not bound to pinned CPython source"]
    entries = mapping.get("inputs")
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        return ["Missing or invalid mapping input inventory"]
    ids = [e.get("id") for e in entries]
    if (
        any(not isinstance(k, str) or not k for k in ids)
        or len(ids) != len(set(ids))
        or not MAPPING_REQUIRED_IDS.issubset(ids)
    ):
        return ["Mapping source IDs missing, duplicated or invalid"]
    blockers = []
    for entry in entries:
        source_id, status = entry["id"], entry.get("review_status")
        if status not in MAPPING_PENDING | MAPPING_RESOLVED:
            # A publication-blocker, unresolved status or unknown status fails.
            blockers.append(f"Mapping {source_id}: unresolved/unknown status {status}")
            continue
        if source_id not in MAPPING_PERMISSION_BLOCKERS and status in MAPPING_PENDING:
            continue
        if status not in MAPPING_RESOLVED:
            blockers.append(f"Mapping {source_id}: independent source resolution required")
            continue
        result = entry.get("resolution")
        if not isinstance(result, dict):
            blockers.append(f"Mapping {source_id}: missing source-specific resolution")
            continue
        basis, scope, risk = (
            result.get("basis"), result.get("verified_scope"),
            result.get("remaining_risk"),
        )
        if (
            result.get("status") != status
            or result.get("source_id") != source_id
            or result.get("source_archive_sha256") != pinned_source_sha
            or login(result.get("owner")) != OWNER
            or not reference(result.get("evidence_reference"))
            or not reference(result.get("independent_review_reference"))
            or not isinstance(basis, str) or len(basis.strip()) < 24
            or not isinstance(scope, str) or len(scope.strip()) < 12
            or not isinstance(risk, str) or len(risk.strip()) < 12
        ):
            blockers.append(
                f"Mapping {source_id}: incomplete source-bound licence/removal "
                "evidence and independent review"
            )
    return blockers


def evaluate(facts, record=None):
    """Treat approval fields as record claims; authority_verified is always false.

    PUBLICATION_REVIEW.md requires a human to open and authenticate every reference
    before using this output. An offline validator cannot enforce that human act.
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
    blockers.extend(mapping_blockers(
        facts.get("mapping_attribution"), facts.get("mapping_source_sha256")
    ))
    if facts.get("source_clean") is not True:
        blockers.append("Reviewed build inputs are modified or untracked")
    tools = record.get("implementer_tools", [])
    if not isinstance(tools, list) or {tool(t) for t in tools} != IMPLEMENTER_TOOLS:
        blockers.append(
            "Implementer tool list must match the task's complete implementing-tool inventory"
        )
    if facts.get("source_mode") != "hash-verified-self-hosted-archives":
        blockers.append(
            "Publication requires all ten verified same-origin source archives"
        )
    if facts.get("profile") != "website-checker":
        blockers.append("Publication requires the final website-checker artifact")
    if record.get("schema_version") != 2:
        blockers.append("Missing current versioned review record")
    commit = facts.get("commit", "")
    if (
        not isinstance(commit, str)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or record.get("target_commit") != commit
    ):
        blockers.append("Review is absent or stale for the final source commit")
    sha = facts.get("manifest_sha256", "")
    if (
        not isinstance(sha, str)
        or not re.fullmatch(r"[0-9a-f]{64}", sha)
        or record.get("manifest_sha256") != sha
    ):
        blockers.append("Review does not bind this final artifact manifest")
    findings = record.get("findings", {})
    required = P1 | P2 | NEW_P2
    if set(findings) != required:
        blockers.append("All P1/P2 and N-1/N-2/N-3/N-7 require explicit dispositions")
    for finding in sorted(required):
        entry = findings.get(finding, {})
        if not isinstance(entry, dict):
            raise ValueError("Finding disposition must be an object")
        allowed = {"fixed"} if finding in P1 else {"fixed", "owner-risk-accepted"}
        if entry.get("status") not in allowed or not reference(entry.get("evidence")):
            blockers.append(
                finding
                + " lacks a disposition with a repository comment/review reference"
            )
        if (
            finding in {"P2-6", "P2-7", "N-3"}
            or entry.get("status") == "owner-risk-accepted"
        ):
            if (
                not entry.get("verified_scope")
                or not entry.get("remaining_risk")
                or login(entry.get("owner")) != OWNER
            ):
                blockers.append(
                    finding
                    + " requires Owner judgment with verified scope and remaining risk"
                )
    retention = record.get("source_retention", {})
    if (
        login(retention.get("owner")) != OWNER
        or retention.get("minimum_period") != "entire-binary-distribution-period"
        or not reference(retention.get("reference"))
    ):
        blockers.append(
            "Owner source retention commitment with a repository reference is missing"
        )
    for viewpoint in ("implementation-distribution", "integration"):
        if not any(
            isinstance(r, dict)
            and r.get("type") == viewpoint
            and r.get("result") == "accepted"
            and login(r.get("reviewer_login"))
            and login(r.get("reviewer_login")) not in IMPLEMENTER_TOOLS
            and r.get("reviewer_kind") in {"human", "ai-assisted"}
            and (
                (r.get("reviewer_kind") == "human" and r.get("reviewer_tool") is None)
                or (
                    r.get("reviewer_kind") == "ai-assisted"
                    and tool(r.get("reviewer_tool")) in {"claude-code", "kiro"}
                )
            )
            and tool(r.get("reviewer_tool")) not in IMPLEMENTER_TOOLS
            and r.get("target_commit") == commit
            and reference(r.get("reference"))
            for r in record.get("reviews", [])
        ):
            blockers.append(
                "Missing independent final-head " + viewpoint + " review record"
            )
    complete = not blockers
    approval = record.get("publication_approval", {})
    approved = (
        complete
        and login(approval.get("owner")) == OWNER
        and approval.get("target_commit") == commit
        and approval.get("manifest_sha256") == sha
        and approval.get("decision") == "approved"
        and reference(approval.get("reference"))
    )
    if not approved:
        blockers.append(
            "Separate explicit Owner publication approval record is absent or stale"
        )
    return {
        "publication": "record-checks-passed-human-verification-required"
        if approved
        else "blocked",
        "record_shape_and_binding": "passed" if approved else "blocked",
        "authority_verified": False,
        "human_reference_verification_required": True,
        "complete_distribution_audit": complete,
        "public_distribution_approved": approved,
        "approval_field_semantics": "Unverified claims in the supplied record; not authenticated authorization",
        "blockers": blockers,
    }
