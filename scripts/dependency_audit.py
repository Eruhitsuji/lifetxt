#!/usr/bin/env python
"""Create release dependency license and vulnerability evidence."""

from __future__ import print_function

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 compatibility
    import tomli as tomllib


def _run(command, cwd):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("%s failed: %s" % (command[0], result.stderr.strip()))
    return result


def _name(requirement):
    return (
        requirement.split(";", 1)[0]
        .split("[", 1)[0]
        .split(">", 1)[0]
        .split("<", 1)[0]
        .split("=", 1)[0]
        .strip()
        .lower()
        .replace("_", "-")
    )


def generate(root, output):
    root = Path(root).resolve()
    with open(root / "pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)["project"]
    direct = list(project.get("dependencies", []))
    stable_extras = {
        name: values
        for name, values in project.get("optional-dependencies", {}).items()
        if name != "dev"
    }
    direct += [item for values in stable_extras.values() for item in values]
    direct_names = sorted({_name(item) for item in direct})

    with tempfile.TemporaryDirectory(prefix="lifetxt-dependency-audit-") as temp:
        cache = Path(temp) / "cache"
        audit = _run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--cache-dir",
                str(cache),
                "--format=json",
                "--progress-spinner",
                "off",
            ],
            root,
        )
        license_run = _run(
            [sys.executable, "-m", "piplicenses", "--format=json", "--with-urls"], root
        )
    audit_data = json.loads(audit.stdout or "[]")
    vulnerabilities = (
        audit_data.get("dependencies", [])
        if isinstance(audit_data, dict)
        else audit_data
    )
    licenses = json.loads(license_run.stdout or "[]")
    license_by_name = {row["Name"].lower().replace("_", "-"): row for row in licenses}
    direct_rows = []
    for requirement in direct:
        name = _name(requirement)
        row = license_by_name.get(name)
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = None
        direct_rows.append(
            {
                "requirement": requirement,
                "name": name,
                "installed_version": installed,
                "license": row.get("License") if row else None,
                "url": row.get("URL") if row else None,
                "license_disposition": (
                    "metadata indicates no release-blocking permissive license finding;"
                    " retain legal review"
                    if row
                    else "pending until package is installed"
                ),
                "status": "present" if row else "not-installed",
            }
        )
    vuln_rows = [row for row in vulnerabilities if row.get("vulns")]
    skipped = [row for row in vulnerabilities if row.get("skip_reason")]
    evidence = {
        "schema": "lifetxt-dependency-audit-v1",
        "audit_date": date.today().isoformat(),
        "package": {"name": project["name"], "version": project["version"]},
        "scope": {
            "direct_requirements": direct_names,
            "optional_extras": sorted(stable_extras),
            "scanner_is_dev_only": True,
        },
        "direct_dependencies": direct_rows,
        "vulnerability_scan": {
            "tool": "pip-audit",
            "tool_version": version("pip-audit"),
            "vulnerable_packages": vuln_rows,
            "vulnerable_package_count": len(vuln_rows),
            "unscanned_packages": skipped,
            "unscanned_package_count": len(skipped),
        },
        "limitations": [
            "The scan reports advisories known to the selected pip-audit service at audit time.",
            "The local lifetxt package is not published to PyPI and is therefore unscanned by pip-audit.",
            "License values are package metadata declarations, not legal advice.",
        ],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = generate(args.root, args.output)
    print(
        json.dumps(
            {
                "ok": True,
                "audit_date": evidence["audit_date"],
                "vulnerable_package_count": evidence["vulnerability_scan"][
                    "vulnerable_package_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
