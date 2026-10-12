"""Explicit read-only semantic warnings for Project risk records."""

from .projects import SEVERITY_ORDER
from .model import Diagnostic
from .diagnostic_contract import diagnostic_to_output_dict


def validate_risks(items):
    """Preserve permissive records; diagnose only explicitly selected risks."""
    diagnostics = []
    count = 0
    states = {"open", "closed", "resolved", "mitigated", "done"}
    for item in items:
        if str((item.details.get("record") or [""])[0]).lower() != "risk":
            continue
        count += 1

        def warn(code, key, message):
            diagnostics.append(
                diagnostic_to_output_dict(
                    Diagnostic(
                        "warning",
                        code,
                        message,
                        source=item.source,
                        line=item.line,
                        hint="Review %s manually; no values were changed." % key,
                    )
                )
            )

        for key in ("record", "severity", "state"):
            values = item.details.get(key, [])
            if len(values) > 1:
                warn("PRV001", key, "Risk %s has multiple scalar values." % key)
        for value in item.details.get("severity", []):
            if str(value).lower() not in SEVERITY_ORDER:
                warn("PRV002", "severity", "Unrecognized risk severity: %s" % value)
        for value in item.details.get("state", []):
            if value not in states:
                if str(value).lower() in states:
                    warn(
                        "PRV003",
                        "state",
                        "Risk state has noncanonical case: %s" % value,
                    )
                else:
                    warn("PRV004", "state", "Unrecognized risk state: %s" % value)
        if not any(str(v).strip() for v in item.details.get("project", [])):
            warn("PRV005", "project", "Risk has no Project scope.")
    return {
        "contract_version": "1",
        "record_kind": "risk",
        "read_only": True,
        "risk_count": count,
        "diagnostics": diagnostics,
    }


def command_project_validate(args):
    import json
    from . import cli

    items, _ = cli._parse_or_exit(args.paths, cli._config(args))
    result = validate_risks(items)
    if args.format == "json":
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = "Risk records: %d; warnings: %d" % (
            result["risk_count"],
            len(result["diagnostics"]),
        )
        for row in result["diagnostics"]:
            output += "\n%s:%s %s: %s" % (
                row.get("source") or "input",
                row.get("line"),
                row["code"],
                row["message"],
            )
    cli.write_text(None, output + "\n")
    return 0
