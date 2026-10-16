#!/usr/bin/env python3
"""Read-only inventory of the current contract and future branch migration work."""

import argparse
import json
from pathlib import Path
import re
import sys


def valid_branch_name(value):
    if not isinstance(value, str) or not value or value == "@":
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value):
        return False
    if ".." in value or value.endswith("."):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock")
        for part in value.split("/")
    )


def scalar(text, key):
    values = re.findall(r"^\s*" + re.escape(key) + r":\s*([^\s#]+)\s*$", text, re.M)
    if len(values) != 1:
        raise ValueError("Expected one simple scalar for " + key)
    return values[0].strip("\"'")


def inspect(root, candidate=None):
    root = Path(root)
    report = {
        "schema_version": 1,
        "current_contract_ok": False,
        "migration_ready": False,
        "candidate": {"branch": candidate, "state": "deferred"},
        "errors": [],
        "checks": [],
    }
    try:

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate strategy key: " + key)
                result[key] = value
            return result

        strategy = json.loads(
            (root / ".ai/project/BRANCH_STRATEGY.json").read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
        if strategy.get("schema_version") != 1 or strategy.get("mode") != "main-only":
            raise ValueError("Only schema_version 1 / main-only is supported")
        roles = strategy.get("roles")
        if roles != {"integration": "main", "release": "main", "deployment": "main"}:
            raise ValueError(
                "Current integration/release/deployment roles must remain main"
            )
        future = strategy.get("future")
        if not isinstance(future, dict) or future.get("state") != "deferred":
            raise ValueError("Future branch state must remain deferred")
        branch = candidate if candidate is not None else future.get("candidate")
        if not valid_branch_name(branch) or branch in roles.values():
            raise ValueError("Candidate must be a valid distinct branch name")
        report["candidate"]["branch"] = branch
        report["roles"] = roles

        sources = {
            "project": ".ai/project/PROJECT.yml",
            "merge": ".ai/project/MERGE_POLICY.yml",
            "rules": ".ai/project/RULES.md",
            "ci": ".github/workflows/ci.yml",
            "release": ".github/workflows/release.yml",
            "server": "lifetxt/server_update.py",
            "deployment": "docs/deployment/ubuntu-server.md",
        }
        text = {
            key: (root / path).read_text(encoding="utf-8")
            for key, path in sources.items()
        }
        if (
            scalar(text["project"], "default_branch") != "main"
            or scalar(text["merge"], "default_branch") != "main"
        ):
            raise ValueError("Project/merge default branch contradicts current roles")
        if "`base=main`" not in text["rules"]:
            raise ValueError("Explicit final PR base=main rule is missing")
        events = re.search(r"^on:\s*\n(.*?)(?=^\S|\Z)", text["ci"], re.M | re.S)
        push = (
            None
            if events is None
            else re.search(
                r"^  push:\s*\n    branches:\s*\n((?:      - [^\n]+\n?)+)",
                events[1],
                re.M,
            )
        )
        branches = (
            []
            if push is None
            else [line.strip()[2:].strip("\"'") for line in push[1].splitlines()]
        )
        if branches != ["main"]:
            raise ValueError("CI main push branch contract is missing or needs review")
        release_events = re.search(
            r"^on:\s*\n(.*?)(?=^\S|\Z)", text["release"], re.M | re.S
        )
        if release_events is None or re.findall(
            r"^  ([A-Za-z_]+):", release_events[1], re.M
        ) != ["workflow_dispatch"]:
            raise ValueError("Manual-only release entry needs review")
        prepare = re.search(
            r"^  prepare:\s*\n(.*?)(?=^  [A-Za-z_-]+:|\Z)",
            text["release"],
            re.M | re.S,
        )
        if prepare is None or not re.search(
            r"^    if: github.ref == 'refs/heads/main' && github.repository == 'Eruhitsuji/lifetxt'\s*$",
            prepare[1],
            re.M,
        ):
            raise ValueError("Main-only release preparation guard needs review")
        if "FETCH_HEAD" not in text["server"] or '"--ff-only"' not in text["server"]:
            raise ValueError(
                "server-update resolved-ref / fast-forward contract needs review"
            )
        if (
            '"branch": "main"' not in text["deployment"]
            or '"ref": "main"' not in text["deployment"]
        ):
            raise ValueError("Explicit main server-update runbook is missing")

        def check(name, status, evidence, action):
            report["checks"].append(
                {"name": name, "status": status, "evidence": evidence, "action": action}
            )

        check(
            "CI routing and gates",
            "change_required",
            sources["ci"],
            f"Design push verification for {branch}; audit event/ref conditions and aggregate gates before enabling it.",
        )
        check(
            "AI final PR destination",
            "change_required",
            sources["rules"],
            f"Explicitly define feature -> {branch} and {branch} -> main task contracts and traceability.",
        )
        check(
            "Branch roles and merge policy",
            "change_required",
            sources["merge"],
            "Review integration vs release/default roles; changing this metadata alone changes no behavior.",
        )
        check(
            "Release provenance",
            "manual_required",
            sources["release"],
            "Verify tags remain approved immutable release revisions from main; candidate CI is not release approval.",
        )
        check(
            "Candidate server and data separation",
            "manual_required",
            sources["deployment"],
            f"Plan an isolated checkout/data/service for {branch}; inspect branch, ref, fixed SHA, backup and health checks.",
        )
        check(
            "GitHub protection and review authority",
            "manual_required",
            "GitHub repository settings (not queried)",
            "Review rulesets, required checks, review freshness and promotion authority for both branches.",
        )
        check(
            "Promotion and rollback acceptance",
            "manual_required",
            "Future design Issue / human decision",
            "Define main promotion evidence, rollback ownership and adoption approval before creating the candidate branch.",
        )
        report["current_contract_ok"] = True
    except (OSError, ValueError, TypeError, AttributeError) as error:
        report["errors"].append(str(error))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument(
        "--candidate", help="Preview a future candidate name; no branch is created"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = inspect(args.root, args.candidate)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(
            "Current main-only contract: "
            + ("consistent" if report["current_contract_ok"] else "ERROR")
        )
        print(
            "Future candidate: "
            + str(report["candidate"]["branch"])
            + " (deferred; migration not approved)"
        )
        for error in report["errors"]:
            print("ERROR: " + error)
        for check in report["checks"]:
            print(
                f"[{check['status']}] {check['name']}: {check['action']} ({check['evidence']})"
            )
    return 0 if report["current_contract_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
