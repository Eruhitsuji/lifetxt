"""Pure failure policy shared by release receipts and offline simulations."""


def classify(
    *, published, same_bytes=False, source_defect=False, external=False, critical=False
):
    if critical:
        return {
            "kind": "critical_blocker",
            "resume": "human_decision",
            "latest_allowed": False,
        }
    if external:
        return {
            "kind": "external_manual_required",
            "resume": "external_submission",
            "latest_allowed": True,
        }
    if not published:
        return {
            "kind": "preflight_failure",
            "resume": "new_preflight_same_unpublished_version_allowed",
            "latest_allowed": False,
        }
    if source_defect or not same_bytes:
        return {
            "kind": "published_source_defect",
            "resume": "new_human_selected_version",
            "latest_allowed": False,
        }
    return {
        "kind": "publish_retryable",
        "resume": "incomplete_stage_same_bytes_only",
        "latest_allowed": False,
    }
