"""Reproduce retained source/release relationships without building executable code."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from contrib.browser_check_poc.notice_inventory import validate_notices
from contrib.browser_check_poc.source_delivery import (
    SOURCE,
    load_lock,
    read_members,
    safe_path,
    validate_cache,
)


def names(entry, cache):
    with tarfile.open(cache / entry["file"]) as archive:
        prefix = entry["root"] + "/"
        return {
            m.name.removeprefix(prefix)
            for m in archive
            if m.isfile() and m.name.startswith(prefix)
        }


def patch_member_paths(data):
    result = set()
    for header in re.findall(r"^(?:---|\+\+\+) ([^\n\t]+)", data.decode(), re.M):
        if header == "/dev/null":
            continue
        if not header.startswith(("a/", "b/")):
            raise ValueError(
                "Patch paths must be relative to the retained CPython tree"
            )
        path = header[2:]
        safe_path(path)
        result.add(path)
    return result


def validate_generated_sysconfig(name, raw, lock):
    """Hash and inspect the generated source without executing its Python code."""
    expected = lock["generated_sysconfig"]
    if (
        name != expected["file"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
    ):
        raise ValueError("Unknown generated sysconfig source")
    tree = ast.parse(raw)
    assignments = [
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "build_time_vars"
    ]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Dict):
        raise ValueError("Unexpected sysconfig source shape")
    dictionary = assignments[0].value
    values = {
        ast.literal_eval(k): v for k, v in zip(dictionary.keys, dictionary.values)
    }
    for key, value in expected["required_values"].items():
        if key not in values or ast.literal_eval(values[key]) != value:
            raise ValueError("Sysconfig source contradicts runtime build policy")


def observe_runtime(runtime, source, entries):
    result = subprocess.run(
        ["node", str(source / "runtime_probe.mjs"), str(runtime)],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    observed = json.loads(result.stdout)
    if observed != {
        "sqlite": entries["sqlite"]["version"],
        "zstd": entries["zstd"]["version"],
        "ucd": "16.0.0",
        "legacy_ucd": "3.2.0",
        "with_mimalloc": 1,
    }:
        raise ValueError("Actual WASM versions differ from retained source inventory")
    return observed


def probe(cache, runtime, output, source=SOURCE):
    lock = load_lock(source)
    validate_cache(cache, lock, include_core=True)
    validate_notices(source, runtime)
    entries = {e["id"]: e for e in lock["archives"]}
    observed = observe_runtime(runtime, source, entries)
    core = entries["upstream-core"]
    data = read_members(cache / core["file"], core["root"], core["required_members"])
    if any(data[n] != (runtime / n).read_bytes() for n in data):
        raise ValueError("Runtime differs from official core release")
    pyodide = entries["pyodide"]
    cpython = entries["cpython"]
    py_names = names(pyodide, cache)
    cp_names = names(cpython, cache)
    patches = sorted(
        n for n in pyodide["required_members"] if n.startswith("cpython/patches/")
    )
    py_members = set(patches)
    with zipfile.ZipFile(runtime / "python_stdlib.zip") as archive:
        shipped = {
            n: archive.read(n) for n in archive.namelist() if not n.endswith("/")
        }
    py_members |= {"src/py/" + n for n in shipped if "src/py/" + n in py_names}
    py_data = read_members(cache / pyodide["file"], pyodide["root"], py_members)
    cp_members = {"Lib/" + n for n in shipped if "Lib/" + n in cp_names}
    touched = set()
    for name in patches:
        touched |= patch_member_paths(py_data[name])
    cp_members |= touched & cp_names
    cp_data = read_members(cache / cpython["file"], cpython["root"], cp_members)
    if not shutil.which("patch"):
        raise RuntimeError(
            "Patch utility is required to verify all upstream CPython patches"
        )
    emscripten = entries["emscripten"]
    ports = read_members(
        cache / emscripten["file"],
        emscripten["root"],
        ["tools/ports/zlib.py", "tools/ports/bzip2.py"],
    )
    port_checks = []
    for ident in ("zlib", "bzip2"):
        expected = re.search(
            r"HASH = '([0-9a-f]+)'", ports["tools/ports/" + ident + ".py"].decode()
        ).group(1)
        actual = hashlib.sha512(
            (cache / entries[ident]["file"]).read_bytes()
        ).hexdigest()
        if actual != expected or actual != entries[ident]["recipe_sha512"]:
            raise ValueError("Source bytes differ from Emscripten port pin")
        port_checks.append(
            {"component": ident, "recipe_sha512": actual, "result": "matched"}
        )
    recipes = read_members(
        cache / pyodide["file"], pyodide["root"], ["Makefile.envs", "cpython/Makefile"]
    )
    expected_python = re.search(
        r"PYTHON_ARCHIVE_SHA256=([0-9a-f]+)", recipes["Makefile.envs"].decode()
    ).group(1)
    if expected_python != cpython["sha256"]:
        raise ValueError("CPython source differs from recipe SHA256")
    for component, variable in (
        ("hiwire", "HIWIRE_COMMIT"),
        ("libffi", "LIBFFI_COMMIT"),
    ):
        if (
            f"{variable}={entries[component]['version']}"
            not in recipes["cpython/Makefile"].decode()
        ):
            raise ValueError("Source revision differs from upstream build recipe")
    patch_results = []
    with tempfile.TemporaryDirectory() as directory:
        working = Path(directory)
        for name in touched:
            path = working / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name in cp_data:
                path.write_bytes(cp_data[name])
        for name in patches:
            patch = working / Path(name).name
            patch.write_bytes(py_data[name])
            result = subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)],
                cwd=working,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode:
                raise ValueError("Upstream patch failed clean application: " + name)
            patch_results.append(
                {
                    "member": name,
                    "sha256": hashlib.sha256(py_data[name]).hexdigest(),
                    "application": "passed-no-fuzz",
                }
            )
        mapping = []
        counts = {}
        for name, raw in sorted(shipped.items()):
            if "src/py/" + name in py_data and py_data["src/py/" + name] == raw:
                category, member = "pyodide-source-identical", "src/py/" + name
            elif cp_data.get("Lib/" + name) == raw:
                category, member = "cpython-source-identical", "Lib/" + name
            elif (working / "Lib" / name).is_file() and (
                working / "Lib" / name
            ).read_bytes() == raw:
                category, member = "cpython-source-plus-upstream-patches", "Lib/" + name
            elif name == lock["generated_sysconfig"]["file"]:
                validate_generated_sysconfig(name, raw, lock)
                category, member = (
                    "generated-build-configuration-source-shipped-in-stdlib",
                    "cpython/Makefile sysconfigdata target",
                )
            else:
                raise ValueError("Unmapped or changed stdlib source: " + name)
            counts[category] = counts.get(category, 0) + 1
            mapping.append(
                {
                    "file": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "basis": category,
                    "source_member": member,
                }
            )
    # Extra notices must reproduce the checked source documents/comment selections.
    provenance = json.loads((source / "notices/provenance.json").read_text("utf-8"))
    notice_checks = []
    for notice in provenance["files"]:
        if not notice.get("source_members"):
            continue
        fragments = {}
        by_archive = {}
        for member in notice["source_members"]:
            by_archive.setdefault(member["archive"], []).append(member)
        for ident, members in by_archive.items():
            e = entries[ident]
            source_data = read_members(
                cache / e["file"], e["root"], [m["member"] for m in members]
            )
            for member in sorted(members, key=lambda m: m["member"]):
                raw = source_data[member["member"]]
                if hashlib.sha256(raw).hexdigest() != member["sha256"]:
                    raise ValueError("Notice source member mismatch")
                text = raw.decode("utf-8")
                if notice["selection"] == "leading-line-comments":
                    text = re.match(r"(?:#[^\n]*\n|\n)*", text).group()
                if notice["selection"] == "headers":
                    text = re.match(r"\s*(/\*.*?\*/)", text, re.S).group(1) + "\n"
                fragments.setdefault(text, []).append(member["member"])
        expected = (
            "".join(fragments)
            if notice["selection"] == "whole"
            else "\n".join(
                "Source members: " + ", ".join(n) + "\n" + t
                for t, n in fragments.items()
            )
        )
        if (source / "notices" / notice["file"]).read_text("utf-8") != expected:
            raise ValueError("Notice selection differs from source archive")
        notice_checks.append(
            {
                "notice": notice["file"],
                "members": len(notice["source_members"]),
                "result": "source-bytes-verified",
            }
        )
    report = {
        "issue": 1409,
        "runtime_release_identity": "5/5 byte-identical; no local runtime byte modifications",
        "release_archive_sha256": core["sha256"],
        "port_archive_checks": port_checks,
        "runtime_observations": observed,
        "archive_correspondence": [
            {
                "component": e["id"],
                "basis": e["correspondence_basis"],
                "archive_sha256": e["sha256"],
                "limit": "Local archive hash alone is not an upstream binary build attestation",
                **(
                    {"official_equivalence": e["official_equivalence"]}
                    if "official_equivalence" in e
                    else {}
                ),
            }
            for e in lock["archives"]
        ],
        "runtime_files": json.loads(
            (source / "notices/components.json").read_text("utf-8")
        )["runtime_observations"]["runtime_files"],
        "source_lock_sha256": hashlib.sha256(
            (source / "source-lock.json").read_bytes()
        ).hexdigest(),
        "pyodide_source_commit": lock["pyodide_commit"],
        "cpython_patch_checks": patch_results,
        "stdlib_counts": counts,
        "stdlib_mapping": mapping,
        "additional_notices": notice_checks,
        "mapping_attribution_sha256": hashlib.sha256(
            (source / "notices/mapping-attribution.json").read_bytes()
        ).hexdigest(),
        "complete_distribution_audit": False,
        "public_distribution_approved": False,
        "remaining_review": [
            "Independent evaluation of complete WASM/file attribution and Unicode mapping scope; known Unicode notices now retained",
            "Upstream recipes/release are not signed build or bit-reproducibility attestation",
            "Independent distribution/implementation/integration acceptance and Owner publication approval",
        ],
    }
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = probe(args.cache, args.runtime, args.output)
    print(
        json.dumps(
            {
                "runtime": result["runtime_release_identity"],
                "patches": len(result["cpython_patch_checks"]),
                "stdlib": result["stdlib_counts"],
            }
        )
    )
