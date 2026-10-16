"""Read actual public distributions, generate adapters, then promote only verified bytes."""

import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import generate_conda_recipe as conda
import generate_homebrew_formula as homebrew
import generate_scoop_manifest as scoop
import generate_winget_manifest as winget
import release_canonical as canonical
import release_preflight_core as core
import release_preflight_mini as mini
import release_preflight_proof as proof
import release_preflight_standalone as standalone
import release_remote as remote
from lifetxt.versioning import release_parts


def verify_github(api, plan, public, output):
    release = api.optional("/releases/tags/" + plan["candidate"]["tag"])
    proof.require(
        release is not None
        and api.tag_source(plan["candidate"]["tag"]) == plan["candidate"]["source_sha"],
        "public release/tag missing or changed",
    )
    rows = canonical.staged_rows(public)
    assets = api.assets(release)
    canonical.remote_inventory(rows, assets, True)
    output = Path(output)
    output.mkdir(parents=True)
    expected = {r["name"]: r for r in rows}
    prefix = (
        "https://github.com/Eruhitsuji/lifetxt/releases/download/"
        + plan["candidate"]["tag"]
        + "/"
    )
    for asset in assets:
        name = asset["name"]
        proof.require(
            asset["browser_download_url"] == prefix + urllib.parse.quote(name, safe=""),
            "unexpected public download URL",
        )
        raw = remote.fetch(asset["browser_download_url"])
        canonical.bytes_match(raw, expected[name])
        (output / name).write_bytes(raw)
    canonical.staged_rows(output)
    inventory = proof.load(output / "release-inventory.json")
    for row in inventory["assets"]:
        if row["role"] in ("wheel", "sdist"):
            metadata = core.package_metadata(output / row["name"])
            proof.require(
                metadata["Name"] == "lifetxt"
                and metadata["Version"] == plan["candidate"]["version"],
                "downloaded package metadata mismatch",
            )
    return release


def public_smoke(plan, downloaded, source):
    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(
            {
                k: v
                for k, v in saved.items()
                if k in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}
            }
        )
        _public_smoke(plan, downloaded, source)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _public_smoke(plan, downloaded, source):
    """Fresh remote bytes on representative native Linux; preflight covers all 13."""
    root = Path(downloaded)
    binary = root / "lifetxt-linux-x86_64"
    binary.chmod(0o755)
    standalone.validate_host("standalone-linux-x86_64")
    standalone.smoke(
        binary.resolve(),
        Path(source).resolve() / "examples/minimal_life.txt",
        plan["candidate"]["version"],
    )
    inventory = proof.load(root / "release-inventory.json")
    name = next(
        r["name"]
        for r in inventory["assets"]
        if r["role"] == "binary" and r["targets"] == ["mini-linux-x86_64"]
    )
    binary = root / name
    binary.chmod(0o755)
    mini.static_elf(binary, "mini-linux-x86_64")
    mini.smoke(binary.resolve(), Path(source).resolve(), plan["candidate"])


def generate(plan, downloaded, output):
    root, output = Path(downloaded), Path(output)
    checksums = canonical.parse_checksums((root / "SHA256SUMS").read_bytes())
    version = plan["candidate"]["version"]
    formula = homebrew.build_formula(version, checksums, "Eruhitsuji/lifetxt")
    output.mkdir(parents=True)
    (output / "lifetxt.rb").write_text(formula, encoding="utf-8", newline="\n")
    windows = "lifetxt-windows-x86_64.exe"
    url = (
        "https://github.com/Eruhitsuji/lifetxt/releases/download/"
        + plan["candidate"]["tag"]
        + "/"
        + windows
    )
    winget.generate(version, url, checksums[windows], output / "winget")
    proof.write_new(
        output / "scoop.json", scoop.build_manifest(version, url, checksums[windows])
    )
    sdist = next(
        r
        for r in proof.load(root / "release-inventory.json")["assets"]
        if r["role"] == "sdist"
    )
    (output / "meta.yaml").write_text(
        conda.build_meta_yaml(version, sdist["sha256"]), encoding="utf-8", newline="\n"
    )
    return {
        "winget": "generated",
        "scoop": "generated",
        "conda": "generated",
        "external_submission": "manual_required",
    }


def tap_api(method, value=None):
    if not os.environ.get("HOMEBREW_TAP_TOKEN"):
        raise remote.TransportError("Homebrew blocked: HOMEBREW_TAP_TOKEN is missing")
    env = {**os.environ, "GH_TOKEN": os.environ["HOMEBREW_TAP_TOKEN"]}
    args = [
        "gh",
        "api",
        "--method",
        method,
        "/repos/Eruhitsuji/homebrew-tap/contents/Formula/lifetxt.rb",
    ]
    if value is not None:
        args += ["--input", "-"]
    try:
        result = subprocess.run(
            args,
            input=None if value is None else json.dumps(value).encode(),
            env=env,
            capture_output=True,
            check=True,
            timeout=120,
        )
    except subprocess.SubprocessError:
        raise remote.TransportError(
            "Homebrew blocked: check transport and existing token Contents read/write on Eruhitsuji/homebrew-tap"
        ) from None
    return json.loads(result.stdout)


def publish_homebrew(plan, generated):
    content = (Path(generated) / "lifetxt.rb").read_bytes()
    before = tap_api("GET")
    current = base64.b64decode(before["content"])
    if current != content:
        versions = re.findall(rb'^  version "([0-9.]+)"$', current, re.M)
        proof.require(
            len(versions) == 1
            and release_parts(versions[0].decode())
            < release_parts(plan["candidate"]["version"]),
            "Homebrew same-version conflict or downgrade; never overwrite",
        )
        tap_api(
            "PUT",
            {
                "message": "lifetxt " + plan["candidate"]["tag"],
                "content": base64.b64encode(content).decode(),
                "sha": before["sha"],
                "branch": "main",
            },
        )
    after = tap_api("GET")
    proof.require(
        base64.b64decode(after["content"]) == content,
        "Homebrew remote content mismatch",
    )
    return {
        "state": "verified",
        "repository": "Eruhitsuji/homebrew-tap",
        "blob_sha": after["sha"],
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def no_latest_regression(api, plan):
    latest = api.optional("/releases/latest")
    if latest is not None:
        proof.require(
            latest["tag_name"].startswith("v")
            and release_parts(latest["tag_name"][1:])
            <= release_parts(plan["candidate"]["version"]),
            "older retry cannot move Latest backwards",
        )


def alias_versions(registry, data):
    """Read runnable versions in legacy Docker indexes, excluding only known
    BuildKit attestation descriptors referencing those exact runnable manifests.
    docker/metadata-action's first raw tag can label the image with leading v.
    """
    rows = json.loads(data).get("manifests", [])
    runnable = [
        r
        for r in rows
        if r.get("platform")
        in (
            {"os": "linux", "architecture": "amd64"},
            {"os": "linux", "architecture": "arm64"},
            {"os": "linux", "architecture": "amd64", "variant": "v1"},
            {"os": "linux", "architecture": "arm64", "variant": "v8"},
        )
    ]
    proof.require(
        len(runnable) == 2
        and {r["platform"]["architecture"] for r in runnable} == {"amd64", "arm64"},
        "cannot establish both alias platform versions",
    )
    digests = {r["digest"] for r in runnable}
    proof.require(
        len(rows) == len({r["digest"] for r in rows}),
        "duplicate alias manifest descriptor",
    )
    for row in rows:
        if row in runnable:
            continue
        annotations = row.get("annotations", {})
        proof.require(
            row.get("platform") == {"os": "unknown", "architecture": "unknown"}
            and row.get("mediaType") == "application/vnd.oci.image.manifest.v1+json"
            and annotations.get("vnd.docker.reference.type") == "attestation-manifest"
            and annotations.get("vnd.docker.reference.digest") in digests,
            "unknown/unbound legacy alias descriptor",
        )
    versions = []
    for row in runnable:
        raw = registry.manifest(row["digest"])
        proof.require(
            "sha256:" + hashlib.sha256(raw).hexdigest() == row["digest"]
            and len(raw) == row["size"],
            "alias manifest bytes mismatch",
        )
        descriptor = json.loads(raw)["config"]
        raw = registry.blob(descriptor["digest"])
        proof.require(
            "sha256:" + hashlib.sha256(raw).hexdigest() == descriptor["digest"]
            and len(raw) == descriptor["size"],
            "alias config bytes mismatch",
        )
        version = json.loads(raw)["config"]["Labels"][
            "org.opencontainers.image.version"
        ]
        parts = release_parts(version[1:] if version.startswith("v") else version)
        versions.append(parts)
    proof.require(len(set(versions)) == 1, "mixed alias platform versions")
    return versions


def promote(api, registry, plan, receipt):
    proof.require(
        receipt["plan_digest"] == plan["digest"]
        and receipt["source_sha"] == plan["candidate"]["source_sha"]
        and receipt["version"] == plan["candidate"]["version"],
        "acceptance receipt belongs to another release plan",
    )
    proof.require(
        receipt["state"] == "verified"
        and all(
            receipt["channels"].get(k) == "verified"
            for k in ("github", "pypi", "ghcr", "native")
        )
        and receipt["channels"]["homebrew"]["state"] == "verified"
        and all(
            receipt["channels"].get(k) == "generated"
            for k in ("winget", "scoop", "conda")
        ),
        "required release gate incomplete",
    )
    no_latest_regression(api, plan)
    c = plan["candidate"]
    # Check every alias before any mutation. Exact expected index enables repair
    # after partial alias promotion; a newer alias is never rolled backwards.
    aliases = (
        "latest",
        str(c["version_parts"][0]),
        ".".join(map(str, c["version_parts"][:2])),
    )
    for alias in aliases:
        data = registry.manifest(alias, missing=True)
        if data is None:
            continue
        for parts in alias_versions(registry, data):
            proof.require(
                parts <= tuple(c["version_parts"]),
                "newer registry alias cannot be downgraded",
            )
            proof.require(
                parts != tuple(c["version_parts"])
                or "sha256:" + hashlib.sha256(data).hexdigest()
                == plan["oci_index_digest"],
                "same-version alias points to conflicting bytes",
            )
    registry.login()
    for alias in aliases:
        current = registry.manifest(alias, missing=True)
        if (
            current is None
            or "sha256:" + hashlib.sha256(current).hexdigest()
            != plan["oci_index_digest"]
        ):
            remote.command(
                "skopeo",
                "copy",
                "--all",
                "--preserve-digests",
                "docker://" + remote.IMAGE + "@" + plan["oci_index_digest"],
                "docker://" + remote.IMAGE + ":" + alias,
            )
        proof.require(
            "sha256:" + hashlib.sha256(registry.manifest(alias)).hexdigest()
            == plan["oci_index_digest"],
            "partial alias promotion; retry same plan",
        )
    no_latest_regression(api, plan)
    release = api.optional("/releases/tags/" + c["tag"])
    api.patch("/releases/%s" % release["id"], {"make_latest": "true"})
    proof.require(
        api.get("/releases/latest")["tag_name"] == c["tag"],
        "Latest promotion not confirmed",
    )


def receipt(plan, state, channels, stage):
    return {
        "schema_version": 1,
        "plan_digest": plan["digest"],
        "source_sha": plan["candidate"]["source_sha"],
        "version": plan["candidate"]["version"],
        "run_url": "https://github.com/Eruhitsuji/lifetxt/actions/runs/%s"
        % plan["run_id"],
        "run_attempt": plan["run_attempt"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "stage": stage,
        "channels": channels,
        "desktop_gui_matrix": "not_verified",
        "external_submission": "manual_required",
    }
