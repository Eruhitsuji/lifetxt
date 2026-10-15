"""Read-only Actions API/ZIP boundary for the trusted preflight collector."""

import json
import re
import shutil
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import release_preflight_proof as proof

REPOSITORY = "Eruhitsuji/lifetxt"
WORKFLOW = ".github/workflows/release-preflight.yml"
FAMILIES = ("core", "standalone", "desktop", "mini", "oci")
TITLES = {family: family.capitalize() for family in FAMILIES}
TITLES["oci"] = "OCI"
STEPS = {
    "core": (
        "Build and verify the exact candidate payload",
        "Bind upload reference to verified bytes",
        "Upload immutable non-public Core payload",
        "Upload Core component proof separately",
    ),
    "standalone": (
        "Build and smoke the native frozen executable",
        "Bind upload reference to unchanged frozen bytes",
        "Upload immutable target payload",
        "Upload target proof separately",
    ),
    "desktop": (
        "Stage and verify bundled Core in generated checkout",
        "Build and verify native installer inventory",
        "Bind upload reference to unchanged installer bytes",
        "Upload immutable target payload",
        "Upload target proof and public-name mapping separately",
    ),
    "mini": (
        "Build and verify native static Mini",
        "Bind upload reference to unchanged Mini bytes",
        "Upload immutable target payload",
        "Upload target proof separately",
    ),
    "oci": (
        "Build once and smoke exact native OCI image",
        "Bind upload reference to unchanged OCI graph",
        "Upload immutable target layout",
        "Upload target proof separately",
    ),
}


class Actions:
    """gh handles the authenticated API redirect; no token is logged/stored."""

    def __init__(self, repository=REPOSITORY):
        proof.require(repository == REPOSITORY, "untrusted repository")
        self.base = "/repos/" + repository

    def get(self, path):
        result = subprocess.run(
            ["gh", "api", self.base + path],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        return json.loads(result.stdout, object_pairs_hook=proof.no_duplicate_keys)

    def listing(self, path, key):
        # Slurp ALL pages; never accept the first 100 as a whole inventory.
        result = subprocess.run(
            ["gh", "api", "--paginate", "--slurp", self.base + path + "?per_page=100"],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        pages = json.loads(result.stdout, object_pairs_hook=proof.no_duplicate_keys)
        proof.require(isinstance(pages, list) and bool(pages), "missing API pages")
        rows = [item for page in pages for item in page[key]]
        proof.require(
            all(page["total_count"] == len(rows) for page in pages),
            "incomplete/changing API pagination",
        )
        ids = [proof.positive(item["id"], "API row ID") for item in rows]
        proof.require(len(ids) == len(set(ids)), "duplicate API row ID")
        return rows

    def download(self, artifact, destination):
        with Path(destination).open("xb") as output:
            subprocess.run(
                ["gh", "api", self.base + "/actions/artifacts/%s/zip" % artifact["id"]],
                stdout=output,
                stderr=subprocess.PIPE,
                check=True,
                timeout=600,
            )
        proof.require(
            Path(destination).stat().st_size == artifact["size_in_bytes"]
            and "sha256:" + proof.file_digest(destination) == artifact["digest"],
            "Actions archive size/digest mismatch",
        )


def instant(value):
    proof.require(
        isinstance(value, str) and value.endswith("Z"), "invalid API timestamp"
    )
    return datetime.fromisoformat(value[:-1] + "+00:00")


def identity(run, sha, workflow, event):
    proof.require(
        run["repository"]["full_name"] == REPOSITORY
        and run["head_repository"]["full_name"] == REPOSITORY,
        "foreign/fork workflow run",
    )
    proof.require(
        run["head_sha"] == sha
        and run["head_branch"] == "main"
        and run["path"] == workflow
        and run["event"] == event,
        "workflow run identity mismatch",
    )


def main_ci(api, source_sha, run_id):
    proof.positive(run_id, "main CI run ID")
    run = api.get("/actions/runs/%s" % run_id)
    identity(run, source_sha, ".github/workflows/ci.yml", "push")
    proof.require(
        run["id"] == run_id
        and run["status"] == "completed"
        and run["conclusion"] == "success",
        "main CI is not successful",
    )
    attempt = proof.positive(run["run_attempt"], "main CI attempt")
    jobs = api.listing("/actions/runs/%s/attempts/%s/jobs" % (run_id, attempt), "jobs")
    gate = [job for job in jobs if job["name"] == "Main compatibility gate"]
    proof.require(
        len(gate) == 1
        and gate[0]["run_id"] == run_id
        and gate[0]["head_sha"] == source_sha
        and gate[0]["status"] == "completed"
        and gate[0]["conclusion"] == "success",
        "missing successful main compatibility gate",
    )
    return {
        "run_id": run_id,
        "run_attempt": attempt,
        "source_sha": source_sha,
        "gate_job_id": gate[0]["id"],
    }


def current_run(api, candidate):
    run = api.get(
        "/actions/runs/%s/attempts/%s" % (candidate["run_id"], candidate["run_attempt"])
    )
    identity(run, candidate["controller_sha"], WORKFLOW, "workflow_dispatch")
    proof.require(
        run["id"] == candidate["run_id"]
        and run["run_attempt"] == candidate["run_attempt"]
        and run["status"] == "in_progress",
        "stale or inactive preflight attempt",
    )
    references = run.get("referenced_workflows", [])
    for family in FAMILIES:
        expected = REPOSITORY + "/.github/workflows/release-preflight-%s.yml" % family
        matched = [
            ref for ref in references if ref["path"].split("@", 1)[0] == expected
        ]
        proof.require(
            len(matched) == 1 and matched[0]["sha"] == candidate["controller_sha"],
            "reusable workflow controller mismatch",
        )
    return run


def producer_jobs(api, candidate):
    jobs = api.listing(
        "/actions/runs/%s/attempts/%s/jobs"
        % (candidate["run_id"], candidate["run_attempt"]),
        "jobs",
    )
    result = {}
    for target in proof.TARGETS:
        family = target.split("-", 1)[0]
        name = (
            TITLES[family]
            + " / "
            + ("core" if family == "core" else "Preflight (%s)" % target)
        )
        matched = [job for job in jobs if job["name"] == name]
        proof.require(len(matched) == 1, "missing/ambiguous producer job: " + target)
        job = matched[0]
        proof.require(
            job["run_id"] == candidate["run_id"]
            and job["head_sha"] == candidate["controller_sha"]
            and job["status"] == "completed"
            and job["conclusion"] == "success",
            "producer did not succeed: " + target,
        )
        for name in STEPS[family]:
            steps = [step for step in job["steps"] if step["name"] == name]
            proof.require(
                len(steps) == 1
                and steps[0]["status"] == "completed"
                and steps[0]["conclusion"] == "success",
                "producer step missing/skipped/failed: " + name,
            )
        proof.require(
            instant(job["started_at"]) <= instant(job["completed_at"]),
            "invalid producer time window",
        )
        result[target] = job
    return result


def artifact_name(candidate, target, kind):
    prefix = "core" if target == "core-any" else target
    return "%s-%s-%s-%s" % (prefix, kind, candidate["run_id"], candidate["run_attempt"])


def select_artifacts(api, candidate, jobs, now=None):
    now = now or datetime.now(timezone.utc)
    rows = api.listing("/actions/runs/%s/artifacts" % candidate["run_id"], "artifacts")
    result = {}
    for target in proof.TARGETS:
        job = jobs[target]
        for kind in ("payload", "proof"):
            name = artifact_name(candidate, target, kind)
            matched = [row for row in rows if row["name"] == name]
            proof.require(len(matched) == 1, "missing/ambiguous artifact: " + name)
            row = matched[0]
            context = row["workflow_run"]
            proof.require(
                context["id"] == candidate["run_id"]
                and context["head_sha"] == candidate["controller_sha"]
                and context["head_branch"] == "main"
                and context["repository_id"] == context["head_repository_id"],
                "foreign artifact workflow identity",
            )
            proof.require(
                row["expired"] is False
                and instant(row["expires_at"]) > now
                and instant(job["started_at"])
                <= instant(row["created_at"])
                <= instant(job["completed_at"])
                <= now,
                "expired/stale-attempt artifact",
            )
            proof.positive(row["id"], "artifact ID")
            size = proof.positive(row["size_in_bytes"], "artifact ZIP size")
            proof.require(
                size <= 8 * 1024**3
                and isinstance(row.get("digest"), str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", row["digest"]),
                "invalid artifact archive descriptor",
            )
            result[(target, kind)] = row
    proof.require(
        len({row["id"] for row in result.values()}) == 2 * len(proof.TARGETS),
        "artifact ID reuse",
    )
    return result


def extract_zip(archive, root, max_bytes=8 * 1024**3):
    """Digest verification precedes this; CRC and path/type checks still apply."""
    root = Path(root)
    proof.require(not root.exists(), "download destination must be fresh")
    root.mkdir(parents=True)
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as source:
        proof.require(0 < len(source.infolist()) <= 512, "artifact ZIP entry limit")
        for member in source.infolist():
            name = member.filename
            proof.require(name.casefold() not in seen, "duplicate/case-alias ZIP path")
            seen.add(name.casefold())
            mode = member.external_attr >> 16
            proof.require(
                not member.is_dir()
                and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                and not member.flag_bits & 1,
                "ZIP directory/link/special/encrypted entry forbidden",
            )
            parts = name.split("/")
            proof.require(
                len(parts) == 1
                and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", name)
                and not name.endswith("."),
                "unsafe ZIP path",
            )
            proof.require(
                not re.fullmatch(
                    r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])",
                    name.split(".")[0],
                    re.IGNORECASE,
                ),
                "reserved ZIP path",
            )
            total += member.file_size
            proof.require(
                member.file_size > 0 and total <= max_bytes,
                "artifact expanded size limit",
            )
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as data, destination.open("xb") as output:
                shutil.copyfileobj(data, output)
            proof.payload_path(root, name)
