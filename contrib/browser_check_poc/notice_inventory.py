"""Validate the bounded notice inventory, never certify legal completeness."""

import hashlib
import json
from pathlib import Path


def validate_notices(source, runtime=None):
    directory = source / "notices"
    provenance = json.loads((directory / "provenance.json").read_text())
    inventory = json.loads((directory / "components.json").read_text())
    if provenance["complete_distribution_audit"] is not False or (
        inventory["complete_distribution_audit"] is not False
        or inventory["public_distribution_approved"] is not False
        or not inventory["remaining_gates"]
    ):
        raise ValueError("This partial investigation cannot approve distribution")
    names = []
    for entry in provenance["files"]:
        name = entry["file"]
        if (
            Path(name).name != name
            or name in names
            or name in ("README.md", "provenance.json", "components.json")
        ):
            raise ValueError("Notice name must be a unique basename")
        if not entry["source_url"].startswith("https://raw.githubusercontent.com/"):
            raise ValueError("Notice provenance must identify the upstream snapshot")
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != (entry["stored_sha256"])
        ):
            raise ValueError("Notice hash mismatch: " + name)
        names.append(name)
    if not names:
        raise ValueError("Notice inventory must not be empty")
    for component in inventory["components"]:
        if component["notice"] is not None and component["notice"] not in names:
            raise ValueError("Component refers to a missing notice")
    if runtime is not None:
        expected_names = {
            "runtime/" + name
            for name in (
                "pyodide.mjs",
                "pyodide.asm.mjs",
                "pyodide.asm.wasm",
                "python_stdlib.zip",
                "pyodide-lock.json",
            )
        }
        if set(inventory["runtime_observations"]["runtime_files"]) != expected_names:
            raise ValueError("Runtime inventory must cover all five shipped files")
        for path, expected in inventory["runtime_observations"][
            "runtime_files"
        ].items():
            name = Path(path).name
            if path != "runtime/" + name:
                raise ValueError("Runtime inventory paths must be flat")
            data = (runtime / name).read_bytes()
            if len(data) != expected["bytes"] or (
                hashlib.sha256(data).hexdigest() != expected["sha256"]
            ):
                raise ValueError("Runtime differs from retained inventory: " + name)
    return sorted(names + ["README.md", "provenance.json", "components.json"])
