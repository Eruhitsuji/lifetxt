"""Fixed HKSCS-free final checker profile; approval remains a separate gate."""

import html
import json
from pathlib import Path
import subprocess
import tempfile

from contrib.browser_check_poc import build as poc
from contrib.browser_check_poc import custom_sources as sources
from contrib.browser_check_poc.artifact_documents import document_bytes
from contrib.browser_check_poc.notice_inventory import (
    validate_notices,
    render_notice_index,
)
from contrib.browser_check_poc.publication_gate import evaluate

PROFILE = "website-checker-hkscs-free"
SOURCE = Path(__file__).resolve().parent
PROOF = SOURCE / "profiles/hkscs-free-1"


DEFAULT_RUNTIME_PROFILE = "lifetxt-hkscs-free-1"
REBUILD_RUNTIME_PROFILE = "lifetxt-hkscs-free-2"
REBUILD_PROFILE = "website-checker-hkscs-free-2"
REBUILD_DESCRIPTOR_SHA256 = (
    "1d297c2097cd5fa8597e79f642223d8bcb9bac05dc293383063d7c80382e9af2"
)


def profile_paths(runtime_profile=None):
    """Finite explicit identities; source recipe 1 is shared, runtime bytes are not."""
    if runtime_profile in (None, DEFAULT_RUNTIME_PROFILE):
        return (
            PROOF,
            PROFILE,
            SOURCE / "hkscs-runtime-observations.json",
            SOURCE / "hkscs-icu-proof.json",
        )
    if runtime_profile != REBUILD_RUNTIME_PROFILE:
        raise ValueError("unknown HKSCS-free runtime profile")
    proof = SOURCE / "profiles/hkscs-free-2"
    descriptor = (proof / "profile.json").read_bytes()
    if sources.sha(descriptor) != REBUILD_DESCRIPTOR_SHA256:
        raise ValueError("profile 2 descriptor drift")
    data = json.loads(descriptor)
    for name, digest in data["evidence_sha256"].items():
        path = proof / name
        if path.is_symlink() or sources.sha(path.read_bytes()) != digest:
            raise ValueError("profile 2 evidence drift: " + name)
    candidate = json.loads((proof / "candidate.json").read_text("utf-8"))
    if (
        data["runtime_profile"] != runtime_profile
        or data["source_recipe_profile"] != DEFAULT_RUNTIME_PROFILE
        or data["candidate_id"] != candidate["candidate_id"]
        or data["runtime_files"] != candidate["files"]
        or candidate["source_recipe"] != DEFAULT_RUNTIME_PROFILE
        or data["complete_distribution_audit"] is not False
        or data["public_distribution_approved"] is not False
    ):
        raise ValueError("profile 2 identity mismatch")
    return (
        proof,
        REBUILD_PROFILE,
        proof / "runtime-observations.json",
        proof / "icu-proof.json",
    )


def runtime_lock(runtime_profile=None):
    proof, _, observations, icu_path = profile_paths(runtime_profile)
    runtime = json.loads((proof / "wasm-proof.json").read_text("utf-8"))["files"]
    build = json.loads((proof / "source-build-proof.json").read_text("utf-8"))
    if runtime_profile == REBUILD_RUNTIME_PROFILE:
        descriptor = json.loads((proof / "profile.json").read_text("utf-8"))
        if (
            runtime != descriptor["runtime_files"]
            or build["profile"] != DEFAULT_RUNTIME_PROFILE
        ):
            raise ValueError("profile 2 runtime/source recipe mismatch")
    lock = {e["id"]: e for e in sources.load_lock()["archives"]}
    if (
        runtime != build["runtime_files"]
        or lock["cpython"]["sha256"] != build["curated_sha256"]
    ):
        raise ValueError("custom runtime/source proofs disagree")
    for member, evidence in (
        ("Makefile", "Pyodide.Makefile"),
        ("cpython/Makefile", "cpython/Makefile"),
        ("cpython/Setup.local", "Pyodide.Setup.local"),
        ("tools/hkscs_free_build.py", "build_helper"),
    ):
        if (
            lock["pyodide"]["required_members"][member]
            != build["inputs_sha256"][evidence]
        ):
            raise ValueError(
                "delivered build source differs from compiled candidate proof"
            )
    observed = json.loads(observations.read_text("utf-8"))
    if (
        observed["runtime_files"] != runtime
        or observed["complete_distribution_audit"] is not False
        or observed["public_distribution_approved"] is not False
    ):
        raise ValueError("custom runtime observations do not match the fixed candidate")
    icu = json.loads(icu_path.read_text("utf-8"))
    if (
        icu["cpython_archive_sha256"] != lock["cpython"]["sha256"]
        or icu["cpython_xml_sha256"]
        != lock["cpython"]["required_members"][icu["source_member"]]
        or icu["base_upstream_cpython_sha256"]
        != lock["cpython"]["base_upstream_sha256"]
        or icu["independent_permission_acceptance"] != "pending"
        or icu["complete_distribution_audit"] is not False
        or icu["public_distribution_approved"] is not False
    ):
        raise ValueError(
            "ICU evidence must bind curated source without granting acceptance"
        )
    return runtime


def check_runtime(directory, runtime_profile=None):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("candidate directory cannot be a symlink")
    for name, row in runtime_lock(runtime_profile).items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing regular candidate runtime input")
        data = path.read_bytes()
        if {"bytes": len(data), "sha256": sources.sha(data)} != row:
            raise ValueError(
                "runtime differs from verified HKSCS-free candidate: " + name
            )


def notice_files(runtime_profile=None):
    proof, _, observations, _ = profile_paths(runtime_profile)
    identity = runtime_profile or DEFAULT_RUNTIME_PROFILE
    names = validate_notices(SOURCE)
    files = {
        name: (
            document_bytes(SOURCE / "notices" / name)
            if name == "README.md"
            else (SOURCE / "notices" / name).read_bytes()
        )
        for name in names
    }
    inventory = json.loads(files["components.json"])
    inventory["runtime_observations"] = {
        "runtime_profile": identity,
        "runtime_files": {
            "runtime/" + k: v for k, v in runtime_lock(runtime_profile).items()
        },
        "evidence": "../sources/wasm-proof.json",
        "versions": json.loads(observations.read_text("utf-8"))["observations"],
        "limits": "Custom source/object/codec verification; full independent distribution acceptance pending",
    }
    inventory["custom_source_delivery"] = "../sources/source-lock.json"
    inventory["issue"] = 1417
    inventory["source_delivery_issue"] = 1417
    for component in inventory["components"]:
        if component["name"] == "Pyodide":
            component.update(
                version="314.0.7 / " + identity,
                basis="fixed custom runtime/source/build proof; not official npm binary identity",
            )
        elif component["name"] == "CPython":
            component.update(
                version="3.14.2 / HKSCS-free",
                basis="curated source plus nine pinned patches and actual compiled/runtime checks",
            )
        elif component["name"] == "HKSCS mapping-derived CJK tables":
            component.update(
                inclusion="removed from custom runtime and corresponding source",
                basis="historical source assessment retained; absence proven by source/object/codec checks",
            )
    helper_notice = "lifetxt-build-helper-MIT.txt"
    files[helper_notice] = (poc.ROOT / "LICENSE").read_bytes()
    inventory["components"].append(
        {
            "name": "lifetxt custom build helper (source only)",
            "version": "lifetxt-hkscs-free-1",
            "licence": "MIT",
            "notice": helper_notice,
            "basis": "tools/hkscs_free_build.py and its original MIT notice are in modified Pyodide source",
        }
    )
    provenance = json.loads(files["provenance.json"])
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=poc.ROOT, text=True
    ).strip()
    provenance["files"].append(
        {
            "file": helper_notice,
            "source_url": f"https://raw.githubusercontent.com/Eruhitsuji/lifetxt/{revision}/LICENSE",
            "source_sha256": sources.sha(files[helper_notice]),
            "stored_sha256": sources.sha(files[helper_notice]),
            "normalization": "Original repository LICENSE bytes, no normalization",
        }
    )
    files["provenance.json"] = sources.json_bytes(provenance)
    inventory["remaining_gates"] = [
        "Independent final-head implementation/distribution and integration acceptance of the custom profile",
        "Independent applicability acceptance of the fixed source-specific ICU grant",
        "Independent acceptance of verified HKSCS removal and retained licence/source completeness",
        "Verify the existing Owner source-retention commitment against the exact custom bundle",
        "Separate explicit publication/deployment approval; only recorded focused desktop Chromium is measured",
    ]
    files["components.json"] = sources.json_bytes(inventory)
    mapping = json.loads((proof / "mapping-attribution.json").read_text("utf-8"))
    entry = next(e for e in sources.load_lock()["archives"] if e["id"] == "cpython")
    if (
        mapping["source_archive_sha256"] != entry["sha256"]
        or mapping["runtime_profile"] != identity
    ):
        raise ValueError("mapping acceptance data must bind the curated profile")
    files["mapping-attribution.json"] = sources.json_bytes(mapping)
    description = (
        b"This directory describes lifetxt-hkscs-free-1, not the unmodified upstream binary.\n"
        if runtime_profile in (None, DEFAULT_RUNTIME_PROFILE)
        else f"This directory describes {identity}, using source recipe lifetxt-hkscs-free-1.\n".encode()
    )
    files["README.md"] = (
        b"# Custom runtime notice inventory\n\n"
        + description
        + b"See index.html for every retained original notice, components.json for the custom\n"
        b"runtime hashes and mapping-attribution.json for source-specific pending acceptance.\n"
        b"HKSCS runtime/data removal is measured; independent acceptance and ICU applicability\n"
        b"remain pending. Corresponding modified/curated sources are in ../sources/.\n"
        b"No notice, source record or Owner claim alone grants publication.\n"
    )
    # The existing renderer preserves every original notice and metadata link.
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "notices").mkdir()
        for name, data in files.items():
            (root / "notices" / name).write_bytes(data)
        files["index.html"] = render_notice_index(root).encode()
    return files


def source_metadata(runtime_profile=None):
    proof, _, observations, icu_path = profile_paths(runtime_profile)
    lock = sources.load_lock()
    if runtime_profile == REBUILD_RUNTIME_PROFILE:
        lock = dict(
            lock,
            runtime_profile=runtime_profile,
            source_recipe_profile=DEFAULT_RUNTIME_PROFILE,
        )
    rows = "".join(
        '<li><a href="'
        + html.escape(e["file"], quote=True)
        + '">'
        + html.escape(e["id"] + " " + e["version"])
        + "</a> SHA256: "
        + e["sha256"]
        + "</li>"
        for e in lock["archives"]
    )
    files = {"source-lock.json": sources.json_bytes(lock)}
    for name in (
        "source-build-proof.json",
        "wasm-proof.json",
        "build-profile.json",
        "source-removal.json",
        "build-environment.json",
    ):
        files[name] = (proof / name).read_bytes()
    if runtime_profile == REBUILD_RUNTIME_PROFILE:
        for name in ("profile.json", "candidate.json", "procurement.json"):
            files[name] = (proof / name).read_bytes()
    files["CUSTOM_SOURCE.md"] = (SOURCE / "CUSTOM_SOURCE.md").read_bytes()
    files["DISTRIBUTION_REMAINING.md"] = (
        SOURCE / "DISTRIBUTION_REMAINING.md"
    ).read_bytes()
    files["HKSCS_FREE.md"] = document_bytes(SOURCE / "HKSCS_FREE.md")
    files["runtime-observations.json"] = observations.read_bytes()
    files["icu-proof.json"] = icu_path.read_bytes()
    if runtime_profile == REBUILD_RUNTIME_PROFILE:
        files["PROFILE.md"] = (proof / "README.md").read_bytes()
        source_profile_label = b"(profile lifetxt-hkscs-free-1)"
        if files["CUSTOM_SOURCE.md"].count(source_profile_label) != 1:
            raise ValueError(
                "custom source guide must identify source recipe exactly once"
            )
        files["CUSTOM_SOURCE.md"] = files["CUSTOM_SOURCE.md"].replace(
            source_profile_label,
            b"(runtime profile lifetxt-hkscs-free-2; source recipe lifetxt-hkscs-free-1)",
        )
        for name in ("HKSCS_FREE.md", "DISTRIBUTION_REMAINING.md"):
            files[name] = (
                b"Profile 2: see PROFILE.md for candidate identity, measured rebuild and remaining acceptance.\n\n"
                + files[name]
            )
    links = "".join(
        '<li><a href="' + name + '">' + name + "</a></li>" for name in sorted(files)
    )
    files["index.html"] = (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Custom runtime sources</title></head><body>
<h1>HKSCS-free source downloads / 対応ソース</h1>
<p>Modified Pyodide Source Code Form remains under MPL-2.0. Other archives retain their original licences and notices.
CPython and Pyodide archives below are derived custom sources, not unchanged official releases. No publication approval is asserted.</p>
<p><a href="../notices/index.html">Third-party notices / ライセンス一覧</a> · <a href="../runtime/python_stdlib.zip">Exact shipped stdlib source</a></p><ul>"""
        + rows
        + links
        + "</ul></body></html>\n"
    ).encode()
    return files


def static_files(runtime_profile=None):
    from scripts.build_website import build as intro
    from scripts.build_website_checker import COPY, SOURCE as checker, render

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "intro"
        intro(root)
        files = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }
    for lang in COPY:
        files[lang + "/check/index.html"] = render(lang).encode()
    for name in ("adapter.py", "limits.mjs", "worker.mjs", "ui.mjs", "checker.css"):
        files["checker/" + name] = (checker / name).read_bytes()
    files["checker/engine.mjs"] = (SOURCE / "engine.mjs").read_bytes()
    files["checker/core.zip"] = poc.core_archive_bytes()
    files.update(
        {"checker/notices/" + k: v for k, v in notice_files(runtime_profile).items()}
    )
    files.update(
        {"checker/sources/" + k: v for k, v in source_metadata(runtime_profile).items()}
    )
    return files


def build(output, runtime, source_cache, runtime_profile=None):
    _, manifest_profile, _, _ = profile_paths(runtime_profile)
    output = Path(output).resolve()
    protected = ("website", "assets", "lifetxt", "scripts", "tests", "contrib", ".ai")
    if output == poc.ROOT or any(
        output.is_relative_to(poc.ROOT / n) for n in protected
    ):
        raise ValueError("custom output must be separate from repository sources")
    if output.exists():
        raise FileExistsError(output)
    if source_cache is None:
        raise ValueError(
            "custom profile requires all ten derived same-origin source archives"
        )
    check_runtime(runtime, runtime_profile)
    sources.validate(source_cache)
    files = static_files(runtime_profile)
    for name in runtime_lock(runtime_profile):
        files["checker/runtime/" + name] = (Path(runtime) / name).read_bytes()
    for entry in sources.load_lock()["archives"]:
        files["checker/sources/" + entry["file"]] = (
            Path(source_cache) / entry["file"]
        ).read_bytes()
    output.mkdir(parents=True)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    poc.write_manifest(
        output,
        ["lifetxt/" + n + ".py" for n in sorted(poc.CORE_MODULES)],
        manifest_profile,
    )
    audit(output, runtime_profile=runtime_profile)


def audit(output, review_record=None, runtime_profile=None):
    output = Path(output)
    if output.is_symlink() or any(p.is_symlink() for p in output.rglob("*")):
        raise ValueError("custom distribution cannot contain symlinks")
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    if runtime_profile is None and manifest.get("profile") == REBUILD_PROFILE:
        runtime_profile = REBUILD_RUNTIME_PROFILE
    _, manifest_profile, _, _ = profile_paths(runtime_profile)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=poc.ROOT, text=True
    ).strip()
    expected_manifest = {
        "pyodide": poc.VERSION,
        "profile": manifest_profile,
        "engine_base_revision": revision,
        "core_modules": ["lifetxt/" + n + ".py" for n in sorted(poc.CORE_MODULES)],
    }
    if {k: v for k, v in manifest.items() if k != "files"} != expected_manifest:
        raise ValueError("custom profile/revision/Core manifest changed")
    check_runtime(output / "checker/runtime", runtime_profile)
    sources.validate(output / "checker/sources")
    expected = {
        name: {"bytes": len(data), "sha256": sources.sha(data)}
        for name, data in static_files(runtime_profile).items()
    }
    expected.update(
        {"checker/runtime/" + k: v for k, v in runtime_lock(runtime_profile).items()}
    )
    expected.update(
        {
            "checker/sources/" + e["file"]: {"bytes": e["bytes"], "sha256": e["sha256"]}
            for e in sources.load_lock()["archives"]
        }
    )
    if manifest["files"] != expected or {
        p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()
    } != set(expected) | {"manifest.json"}:
        raise ValueError(
            "custom artifact allowlist/manifest differs from reviewed source"
        )
    for name, row in expected.items():
        data = (output / name).read_bytes()
        if {"bytes": len(data), "sha256": sources.sha(data)} != row:
            raise ValueError("custom artifact source/hash mismatch: " + name)
    mapping = json.loads(notice_files(runtime_profile)["mapping-attribution.json"])
    clean = not subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "contrib/browser_check_poc",
            "scripts",
            "website",
            "lifetxt",
            "LICENSE",
        ],
        cwd=poc.ROOT,
        text=True,
    ).strip()
    gate = evaluate(
        {
            "profile": "website-checker",
            "source_clean": clean,
            "source_mode": "hash-verified-self-hosted-archives",
            "mapping_attribution": mapping,
            "mapping_source_sha256": mapping["source_archive_sha256"],
            "commit": revision,
            "manifest_sha256": sources.sha((output / "manifest.json").read_bytes()),
        },
        review_record,
    )
    return {
        "issue": 1398,
        "profile": manifest_profile,
        "integrity": "passed",
        **gate,
        "runtime_files": runtime_lock(runtime_profile),
        "source_archives": len(sources.load_lock()["archives"]),
        "source_delivery": "modified Pyodide + curated CPython + eight retained component sources; exact stdlib and Core sources included",
    }
