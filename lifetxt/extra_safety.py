"""Extended CLI commands for release safety and Format 1.0 foundations."""

from __future__ import unicode_literals

import json
import os
import sys

from .doctor import doctor_report
from .extra_common import _json_text, _load_config, _resolved_input_paths, _write_output
from .release_policy import release_gate
from .revision_telemetry import RevisionMetricsStore, store_from_config
from .transaction_journal import (
    abandon_with_backup,
    archive_terminal,
    cleanup_terminal,
    compensate,
    export_evidence,
    inspect_journal,
    journal_directory,
    journal_policy_report,
    list_journals,
    resume,
    verify_backup,
)
from .safety_foundation import (
    CANON_VERSION,
    FORMAT_VERSION,
    audit_python_writes,
    canonical_issues,
    canonicalize_text,
    file_directives,
    format_version_report,
    inspect_locks,
    read_text_exact,
    schema_bundle,
    serve_target_diagnostic,
    stable_diagnostics,
    write_schema_bundle,
)
from .timezone_policy import policy_report


def command_safety(args, config_data):
    action = args.safety_action
    if action == "locks":
        paths = _resolved_input_paths(args.paths, config_data)
        records = inspect_locks(paths, stale_after=args.stale_after)
        return _output({"count": len(records), "locks": records}, args)
    if action == "serve-target":
        paths = _resolved_input_paths(args.paths, config_data)
        write_path = args.write_file
        if not write_path:
            from .config import config_write_file

            write_path = config_write_file(config_data) or (paths[0] if paths else "")
        report = serve_target_diagnostic(paths, write_path)
        return _output(report, args)
    if action == "timezone":
        text = ""
        paths = _resolved_input_paths(args.paths, config_data)
        if paths and paths[0] != "-" and os.path.exists(paths[0]):
            text, _raw, _bom = read_text_exact(paths[0])
        report = policy_report(
            config_data,
            text=text,
            cli_timezone=args.timezone,
            sample=getattr(args, "sample", None),
            fold_policy=getattr(args, "fold_policy", "error"),
            gap_policy=getattr(args, "gap_policy", "error"),
        )
        return _output(report, args, failure=not report.get("valid", False))
    if action == "delegated":
        from .delegated_mutation import (
            apply_delegated_proposal_file,
            prepare_delegated_mutation,
            read_delegated_proposal,
            reject_delegated_proposal_file,
        )

        delegated_action = args.delegated_action
        if delegated_action == "prepare":
            if not getattr(args, "path", None) or not getattr(args, "command", None):
                raise ValueError(
                    "safety delegated prepare requires --path and --command."
                )
            report = prepare_delegated_mutation(
                args.path,
                args.command,
                proposal_path=args.proposal,
                timeout=args.timeout,
                keep_temporary=bool(args.keep_temp),
            )
        elif delegated_action == "inspect":
            proposal, snapshot = read_delegated_proposal(args.proposal)
            report = dict(proposal)
            report["proposal_path"] = snapshot.path
            report["proposal_revision"] = snapshot.content_hash
        elif delegated_action == "apply":
            report = apply_delegated_proposal_file(
                args.proposal,
                expected_proposal_revision=getattr(
                    args, "expected_proposal_revision", None
                ),
                expected_revision=getattr(args, "expected_revision", None),
                unsafe=bool(getattr(args, "unsafe", False)),
            )
        else:
            report = reject_delegated_proposal_file(
                args.proposal,
                expected_proposal_revision=getattr(
                    args, "expected_proposal_revision", None
                ),
                reason=getattr(args, "reason", None),
            )
        return _output(report, args)
    if action == "revisions":
        paths = _resolved_input_paths(args.paths, config_data)
        from .config import config_write_file

        write_path = config_write_file(config_data) or (paths[0] if paths else None)
        store = store_from_config(config_data, writable_path=write_path)
        if getattr(args, "metrics_path", None):
            store = RevisionMetricsStore(
                args.metrics_path,
                mode=store.mode,
                window_days=store.window_days,
            )
        if getattr(args, "reset", False):
            report = store.reset(getattr(args, "expected_hash", None))
        elif getattr(args, "relocate", None):
            report = store.relocate(
                getattr(args, "relocate"),
                expected_hash=getattr(args, "expected_hash", None),
                delete_source=bool(getattr(args, "delete_source", False)),
            )
        else:
            report = store.snapshot()
        report["metrics_revision"] = (
            store.content_hash()
            if os.path.exists(store.path)
            else report.get("metrics_revision")
        )
        if getattr(args, "export_evidence", None):
            report["evidence"] = store.export_evidence(getattr(args, "export_evidence"))
        return _output(report, args)
    if action == "transactions":
        from .config import config_write_file

        write_path = config_write_file(config_data)
        root = os.path.abspath(
            getattr(args, "journal_dir", None)
            or journal_directory(config_data, writable_path=write_path)
        )
        tx_action = getattr(args, "transaction_action", "list")
        if tx_action in (
            "policy-write",
            "policy-migrate",
            "rotate-archives",
            "audit",
            "archive",
            "cleanup",
            "abandon",
            "restore-backup",
        ):
            from .transaction_admin import authorize_operator

            authorize_operator(
                config_data,
                getattr(args, "operator", None),
                action="transactions.%s" % tx_action,
            )
        journal = getattr(args, "journal", None)
        if journal and not os.path.isabs(journal):
            candidate = os.path.join(root, journal)
            journal = (
                candidate
                if candidate.endswith("journal.json")
                else os.path.join(candidate, "journal.json")
            )
        if tx_action == "list":
            rows = list_journals(root, include_terminal=True)
            report = {"journal_dir": root, "count": len(rows), "transactions": rows}
        elif tx_action == "inspect":
            if not journal:
                raise ValueError("transactions inspect requires --journal PATH_OR_ID.")
            report = inspect_journal(journal)
        elif tx_action == "resume":
            if not journal:
                raise ValueError("transactions resume requires --journal PATH_OR_ID.")
            report = resume(journal)
        elif tx_action == "compensate":
            if not journal:
                raise ValueError(
                    "transactions compensate requires --journal PATH_OR_ID."
                )
            report = compensate(journal)
        elif tx_action == "abandon":
            if not journal or not getattr(args, "backup_dir", None):
                raise ValueError(
                    "transactions abandon requires --journal and --backup-dir."
                )
            report = abandon_with_backup(journal, args.backup_dir)
        elif tx_action == "export":
            if not journal or not getattr(args, "output", None):
                raise ValueError("transactions export requires --journal and --output.")
            report = export_evidence(journal, args.output)
            args.output = None
        elif tx_action in (
            "policy",
            "policy-write",
            "policy-migrate",
            "preflight",
            "rotate-archives",
            "audit",
        ):
            from .transaction_admin import (
                append_admin_audit,
                audit_path,
                migrate_policy_file,
                policy_document,
                policy_path,
                preflight_report,
                read_policy_document,
                rotate_archives,
                write_policy_document,
            )

            policy_file = os.path.abspath(
                getattr(args, "policy_file", None)
                or policy_path(root, config=config_data)
            )
            audit_file = os.path.abspath(
                getattr(args, "audit_file", None)
                or audit_path(root, config=config_data)
            )
            operator = getattr(args, "operator", None)
            if tx_action == "policy":
                policy_config = dict(config_data or {})
                tx_config = dict(policy_config.get("transactions") or {})
                tx_config["policy_file"] = policy_file
                policy_config["transactions"] = tx_config
                report = journal_policy_report(root, config=policy_config)
                report["policy_file"] = {
                    "path": policy_file,
                    "document": read_policy_document(
                        policy_file, allow_missing=True, allow_older=True
                    ),
                }
                report["preflight"] = preflight_report(
                    root, config=config_data, create=False
                )
            elif tx_action == "policy-write":
                document = policy_document(config=config_data, operator=operator)
                for assignment in getattr(args, "set", None) or []:
                    if "=" not in assignment:
                        raise ValueError("--set requires KEY=VALUE.")
                    key, value = assignment.split("=", 1)
                    key = key.strip()
                    if key not in document["policy"]:
                        raise ValueError("Unknown transaction policy key: %s" % key)
                    try:
                        value = json.loads(value)
                    except ValueError:
                        pass
                    document["policy"][key] = value
                document["policy"] = __import__(
                    "lifetxt.transaction_policy", fromlist=["policy_from_config"]
                ).policy_from_config({"transactions": document["policy"]})
                report = write_policy_document(
                    policy_file,
                    document,
                    expected_revision=getattr(args, "expected_revision", None),
                    operator=operator,
                    audit_file=audit_file,
                )
            elif tx_action == "policy-migrate":
                report = migrate_policy_file(
                    policy_file,
                    expected_revision=getattr(args, "expected_revision", None),
                    operator=operator,
                    audit_file=audit_file,
                )
            elif tx_action == "preflight":
                report = preflight_report(
                    root, config=config_data, create=bool(getattr(args, "force", False))
                )
            elif tx_action == "rotate-archives":
                if not getattr(args, "archive_dir", None):
                    raise ValueError(
                        "transactions rotate-archives requires --archive-dir."
                    )
                report = rotate_archives(
                    args.archive_dir,
                    max_archives=getattr(args, "max_archives", None)
                    if getattr(args, "max_archives", None) is not None
                    else 100,
                    max_total_bytes=getattr(args, "max_archive_bytes", None)
                    if getattr(args, "max_archive_bytes", None) is not None
                    else 1024 * 1024 * 1024,
                    force=bool(getattr(args, "force", False)),
                    operator=operator,
                    audit_file=audit_file,
                )
            else:
                details = {}
                if getattr(args, "details_json", None):
                    details = json.loads(args.details_json)
                    if not isinstance(details, dict):
                        raise ValueError("--details-json must decode to an object.")
                report = append_admin_audit(
                    audit_file,
                    getattr(args, "event", None) or "manual",
                    operator=operator,
                    details=details,
                    config=config_data,
                )
        elif tx_action == "drill":
            from .fault_drill import SUPPORTED_POINTS, run_fault_drill, run_fault_matrix

            if getattr(args, "matrix", False):
                report = run_fault_matrix(
                    recovery=getattr(args, "recovery", "auto"),
                    keep=bool(getattr(args, "keep_workspace", False)),
                )
            else:
                if not getattr(args, "point", None):
                    raise ValueError(
                        "transactions drill requires --point (%s), or --matrix."
                        % ", ".join(SUPPORTED_POINTS)
                    )
                report = run_fault_drill(
                    args.point,
                    recovery=getattr(args, "recovery", "inspect"),
                    keep=bool(getattr(args, "keep_workspace", False)),
                    repeat_recovery=bool(getattr(args, "repeat_recovery", False)),
                )
        elif tx_action == "archive":
            if not getattr(args, "archive_dir", None):
                raise ValueError("transactions archive requires --archive-dir.")
            report = archive_terminal(
                root,
                args.archive_dir,
                older_than_days=getattr(args, "older_than_days", None)
                if getattr(args, "older_than_days", None) is not None
                else 30.0,
                force=bool(getattr(args, "force", False)),
            )
        elif tx_action == "restore-backup":
            if not getattr(args, "backup_dir", None):
                raise ValueError("transactions restore-backup requires --backup-dir.")
            from .transaction_journal import restore_backup
            from .transaction_admin import audit_path

            report = restore_backup(
                args.backup_dir,
                action=getattr(args, "restore_action", "inspect"),
                working_dir=getattr(args, "working_dir", None),
                operator=getattr(args, "operator", None),
                config=config_data,
                audit_file=getattr(args, "audit_file", None)
                or audit_path(root, config=config_data),
            )
        elif tx_action == "verify-backup":
            if not getattr(args, "backup_dir", None):
                raise ValueError("transactions verify-backup requires --backup-dir.")
            report = verify_backup(args.backup_dir)
        else:
            report = cleanup_terminal(
                root,
                older_than_days=getattr(args, "older_than_days", None),
                force=bool(getattr(args, "force", False)),
                config=config_data,
            )
        failure = bool(report.get("recovery_required") or report.get("errors"))
        return _output(report, args, failure=failure)
    if action == "write-routes":
        root = os.path.abspath(args.root or os.getcwd())
        findings = audit_python_writes(root)
        report = {
            "ok": not findings,
            "root": root,
            "count": len(findings),
            "findings": findings,
        }
        return _output(report, args, failure=bool(findings and args.strict))
    if action == "release-gate":
        root = os.path.abspath(args.root or os.getcwd())
        paths = _resolved_input_paths(args.paths, config_data) if args.paths else []
        report = release_gate(root, paths=paths)
        return _output(report, args, failure=not report["ok"])
    raise ValueError("Unknown safety action: %s" % action)


def command_doctor(args, config_data):
    paths = _resolved_input_paths(args.paths, config_data)
    from .config import config_write_file

    write_path = (
        args.write_file
        or config_write_file(config_data)
        or (paths[0] if paths else None)
    )
    report = doctor_report(
        paths,
        config=config_data,
        write_path=write_path,
        timer_paths=getattr(args, "timer_state", None),
        archive_paths=getattr(args, "archive", None),
        revision_metrics_path=getattr(args, "revision_metrics", None),
        journal_dir=getattr(args, "journal_dir", None),
        cleanup_transactions=getattr(args, "cleanup_transactions", False),
        transaction_retention_days=getattr(args, "transaction_retention_days", 30.0),
        cli_timezone=getattr(args, "timezone", None),
        fold_policy=getattr(args, "fold_policy", "error"),
        gap_policy=getattr(args, "gap_policy", "error"),
        stale_after=getattr(args, "stale_after", 300.0),
        cleanup_stale=getattr(args, "cleanup_stale", False),
        force=getattr(args, "force", False),
    )
    if getattr(args, "support_bundle", None):
        from .support_bundle import write_support_bundle

        bundle = write_support_bundle(report, args.support_bundle)
        report["support_bundle"] = {
            "output": bundle["output"],
            "sha256": bundle["sha256"],
            "redacted": True,
        }
    return _output(report, args, failure=not report["ok"])


def command_format(args, _config_data):
    action = args.format_action
    if action == "info":
        text, _raw, _bom = read_text_exact(args.path)
        directives, duplicates = file_directives(text)
        report = {
            "format": format_version_report(text),
            "canonical_version": CANON_VERSION,
            "directives": directives,
            "duplicate_directives": duplicates,
            "policies": {
                "encoding": "UTF-8 without BOM",
                "line_endings": "LF",
                "unicode": "NFC",
                "detail_keys": "case-sensitive; canonical lowercase",
                "tags_ids_contexts_users_teams_groups_areas_projects": "case-sensitive",
                "metadata_precedence": [
                    "CLI",
                    "file directives",
                    "config",
                    "built-in defaults",
                ],
                "multi_file": "IDs are workspace-unique; input order is authoritative; writes require an explicit target",
            },
        }
        return _output(report, args)
    if action == "check":
        report = stable_diagnostics(args.path)
        return _output(report, args, failure=not report["ok"])
    if action == "canon":
        text, raw, bom = read_text_exact(args.path)
        replacement = canonicalize_text(text)
        issues = canonical_issues(text, raw_bytes=raw, bom=bom, source=args.path)
        changed = replacement != text or bom
        if args.write and changed:
            from .mutation import read_text_snapshot, write_text

            snapshot = read_text_snapshot(args.path)
            write_text(
                args.path,
                replacement,
                expected_hash=snapshot.content_hash,
                operation="format.canon",
                create=False,
            )
        report = {
            "path": args.path,
            "canonical_version": CANON_VERSION,
            "changed": changed,
            "written": bool(args.write and changed),
            "diagnostics": issues,
        }
        if args.output and not args.write:
            _write_output(replacement, args.output)
            report["output"] = args.output
        return _output(
            report, args, failure=bool(issues and args.strict and not args.write)
        )
    if action == "migrate":
        text, _raw, _bom = read_text_exact(args.path)
        version = format_version_report(text)
        if version["state"] == "unsupported":
            report = {
                "path": args.path,
                "source": version,
                "target": FORMAT_VERSION,
                "action": "refuse",
                "changed": False,
                "written": False,
                "reason": "Unsupported source format must be migrated explicitly.",
            }
            return _output(report, args, failure=True)
        if version["state"] == "current":
            replacement = text
            action_name = "noop"
        else:
            replacement = "#! format_version: %s\n%s" % (FORMAT_VERSION, text)
            action_name = "add-format-version"
        changed = replacement != text
        written = False
        if args.write and changed:
            from .mutation import read_text_snapshot, write_text

            snapshot = read_text_snapshot(args.path)
            write_text(
                args.path,
                replacement,
                expected_hash=snapshot.content_hash,
                operation="format.migrate",
                create=False,
            )
            written = True
        if args.output and not args.write:
            _write_output(replacement, args.output)
        return _output(
            {
                "path": args.path,
                "source": version,
                "target": FORMAT_VERSION,
                "action": action_name,
                "changed": changed,
                "written": written,
            },
            args,
        )
    if action == "downgrade":
        text, _raw, _bom = read_text_exact(args.path)
        version = format_version_report(text)
        supported = args.target_version == FORMAT_VERSION
        report = {
            "path": args.path,
            "source": version,
            "target": args.target_version,
            "supported": supported,
            "writable": False,
            "losses": []
            if supported
            else ["No Format 1.0 downgrade mapping is defined."],
        }
        return _output(report, args, failure=not supported)
    if action == "schemas":
        names = write_schema_bundle(args.directory)
        return _output(
            {
                "schema_version": "1",
                "directory": os.path.abspath(args.directory),
                "files": names,
            },
            args,
        )
    raise ValueError("Unknown format action: %s" % action)


def command_capabilities(args, config_data):
    if getattr(args, "surface_matrix", False):
        return command_capability_matrix(args)
    targets = []
    from .config import config_write_file
    from .surface_runtime import capability_document_for

    write_target = config_write_file(config_data)
    if write_target:
        targets.append(os.path.abspath(write_target))
    report = capability_document_for(
        "cli",
        read_only=args.read_only,
        authentication=args.authentication,
        writable_targets=targets,
        config=config_data,
    )
    return _output(report, args)


def command_capability_matrix(args):
    """`lifetxt capabilities --surface-matrix` (#676): additive, read-only
    per-command Web UI/TUI/API/MCP support-state report. Never changes the
    default `lifetxt capabilities` remote-client capability document above.
    """
    from .capability_matrix import matrix_payload, render_matrix_text

    payload = matrix_payload()
    fmt = getattr(args, "format", "json")
    pretty = bool(getattr(args, "pretty", False))
    output = getattr(args, "output", None)
    if fmt == "json":
        text = _json_text(payload, pretty=pretty)
    else:
        text = render_matrix_text(payload["commands"])
    _write_output(text, output)
    return 0


def _output(report, args, failure=False):
    fmt = getattr(args, "format", "json")
    pretty = bool(getattr(args, "pretty", False))
    output = getattr(args, "output", None)
    if fmt == "json":
        text = _json_text(report, pretty=pretty)
    else:
        text = _text_report(report)
    _write_output(text, output)
    return 1 if failure else 0


def _text_report(value, prefix=""):
    lines = []
    if isinstance(value, dict):
        for key, child in value.items():
            label = "%s%s" % (prefix, key)
            if isinstance(child, (dict, list)):
                lines.append(label + ":")
                lines.append(_text_report(child, prefix + "  ").rstrip("\n"))
            else:
                lines.append("%s: %s" % (label, child))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(prefix + "-")
                lines.append(_text_report(child, prefix + "  ").rstrip("\n"))
            else:
                lines.append(prefix + "- " + str(child))
    else:
        lines.append(prefix + str(value))
    return "\n".join(lines) + "\n"
