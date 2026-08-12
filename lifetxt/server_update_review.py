"""Pure server-update diff and review formatting helpers."""


def parse_numstat(text):
    files = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        files.append(
            {
                "path": path,
                "added": None if added == "-" else int(added),
                "removed": None if removed == "-" else int(removed),
            }
        )
    return files


def parse_name_status(text):
    statuses = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            statuses[parts[-1]] = parts[0]
    return statuses


def gather_diff_summary(run_git, repo_root, current, target, timeout, error_cls):
    range_spec = "%s..%s" % (current, target)
    outputs = {}
    for name, args in (
        ("numstat", ["diff", "--no-renames", "--numstat", range_spec]),
        ("name_status", ["diff", "--no-renames", "--name-status", range_spec]),
        ("log", ["log", "--format=%x1e%B", range_spec]),
    ):
        result = run_git(args, cwd=repo_root, timeout=timeout)
        if result.returncode != 0:
            raise error_cls(
                "git %s failed: %s" % (name, (result.stderr or result.stdout).strip()),
                step="risk_classification",
            )
        outputs[name] = result.stdout
    statuses = parse_name_status(outputs["name_status"])
    files = [
        {**entry, "deleted": statuses.get(entry["path"]) == "D"}
        for entry in parse_numstat(outputs["numstat"])
    ]
    return {
        "files": files,
        "commit_messages": [
            msg.rstrip("\n") for msg in outputs["log"].split("\x1e") if msg.strip()
        ],
    }


def classify_risk(diff_summary, trigger_paths, trigger_keywords, excluded_prefixes):
    files = diff_summary.get("files") or []
    messages = diff_summary.get("commit_messages") or []
    reasons = []
    for category, prefixes in trigger_paths.items():
        matched = sorted(
            entry["path"] for entry in files if entry["path"].startswith(prefixes)
        )
        if matched:
            reasons.append("touches %s: %s" % (category, ", ".join(matched)))
    deleted = sorted(entry["path"] for entry in files if entry["deleted"])
    if deleted:
        reasons.append("deletes tracked file(s): %s" % ", ".join(deleted))
    for keyword in trigger_keywords:
        if any(keyword.lower() in message.lower() for message in messages):
            reasons.append("commit message contains %r" % keyword)
    return {
        "changed_file_count": len(files),
        "changed_line_count": sum(
            (e["added"] or 0) + (e["removed"] or 0)
            for e in files
            if e["added"] is not None and not e["path"].startswith(excluded_prefixes)
        ),
        "binary_file_count": sum(1 for e in files if e["added"] is None),
        "reasons": reasons,
    }


def format_review_block(report, server_config_path):
    lines = [
        "===== LIFETXT_UPDATE_REVIEW_BEGIN =====",
        "status=REVIEW_REQUIRED",
        "current=%s" % report["current_commit"],
        "target=%s" % report["target_commit"],
        "commit_count=%s" % report["commit_count"],
        "changed_file_count=%s" % report["changed_file_count"],
        "changed_line_count=%s" % report["changed_line_count"],
        "binary_file_count=%s" % report["binary_file_count"],
        "--- reasons ---",
    ]
    lines.extend(report["review_reasons"] or ["(none)"])
    lines.extend(
        [
            "--- commits ---",
            *(report["commits"] or ["(none)"]),
            "--- changed files ---",
            *(report["changed_files"] or ["(none)"]),
        ]
    )
    lines.extend(
        [
            "--- diff stat ---",
            "%d file(s) changed, %d line(s) changed (%d binary file(s) excluded)"
            % (
                report["changed_file_count"],
                report["changed_line_count"],
                report["binary_file_count"],
            ),
            "--- execution plan ---",
            "installer=%s" % report.get("installer", "pip"),
            "install_command=%s" % " ".join(report.get("install_command") or []),
        ]
    )
    lines.append(
        "service_manager=none"
        if report.get("service_manager") == "none"
        else "service_command=%s" % " ".join(report.get("service_command") or [])
    )
    lines.append(
        "approved_command=lifetxt server-update --server-config %s --approve %s"
        % (server_config_path or "<server-config-path>", report["target_commit"])
    )
    lines.append("===== LIFETXT_UPDATE_REVIEW_END =====")
    return "\n".join(lines)
