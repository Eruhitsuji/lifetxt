"""Authenticate completed preflight and bind one human approval to one run plan."""

import os
import re
import shutil
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import release_canonical as canonical
import release_preflight_actions as actions
import release_preflight_collect as collect
import release_preflight_core as core
import release_preflight_oci_layout as layout
import release_preflight_proof as proof

PLAN_FIELDS = {
    "schema_version",
    "candidate",
    "bundle_digest",
    "artifact",
    "inventory_digest",
    "oci_index_digest",
    "controller_sha",
    "run_id",
    "run_attempt",
}
BUNDLE_FIELDS = {
    "schema_version",
    "candidate_digest",
    "status",
    "publication_authorized",
    "aggregate_digest",
    "main_ci",
    "controller",
    "artifacts",
    "oci_index_digest",
    "files",
}


def extract_bundle(archive, root):
    """Nested final bundles use the same portable-path boundary as proofs."""
    root = Path(root)
    proof.require(not root.exists(), "bundle destination must be fresh")
    root.mkdir(parents=True)
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as source:
        proof.require(0 < len(source.infolist()) <= 2048, "bundle entry limit")
        for member in source.infolist():
            name = member.filename
            proof.require(
                not member.is_dir()
                and stat.S_IFMT(member.external_attr >> 16) in (0, stat.S_IFREG)
                and not member.flag_bits & 1,
                "unsafe bundle ZIP member",
            )
            proof.require(name.casefold() not in seen, "duplicate bundle ZIP member")
            seen.add(name.casefold())
            total += member.file_size
            proof.require(
                member.file_size > 0 and total <= 8 * 1024**3, "bundle size limit"
            )
            destination = root / name
            # Validate before creating anything outside the destination.
            proof.require(
                re.fullmatch(
                    r"[A-Za-z0-9_][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.+-]*)*",
                    name,
                ),
                "unsafe bundle path",
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as data, destination.open("xb") as output:
                shutil.copyfileobj(data, output)
            proof.payload_path(root, name)


def bundle_contents(root, expected_digest):
    candidate = proof.load(root / "candidate.json")
    proof.validate_candidate(candidate)
    manifest = proof.load(root / "preflight-bundle.json")
    proof.unseal(manifest, BUNDLE_FIELDS, "preflight bundle")
    proof.require(
        manifest["digest"] == expected_digest
        and manifest["candidate_digest"] == candidate["digest"]
        and manifest["publication_authorized"] is False
        and manifest["status"] == "preflight_verified",
        "preflight bundle binding mismatch",
    )
    actual = [
        r for r in collect.inventory(root) if r["path"] != "preflight-bundle.json"
    ]
    proof.require(
        actual == manifest["files"], "preflight bundle file inventory mismatch"
    )
    return candidate, manifest


def release_context(controller, context, api):
    proof.require(
        context.get("GITHUB_REPOSITORY") == actions.REPOSITORY
        and context.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and context.get("GITHUB_REF") == "refs/heads/main"
        and context.get("GITHUB_WORKFLOW_REF")
        == actions.REPOSITORY + "/.github/workflows/release.yml@refs/heads/main",
        "release requires trusted manual main workflow",
    )
    sha = context["GITHUB_WORKFLOW_SHA"]
    proof.require(
        not core.git(controller, "status", "--porcelain", "--untracked-files=no"),
        "release controller has tracked changes",
    )
    proof.require(
        proof.SHA.fullmatch(sha)
        and context["GITHUB_SHA"] == sha
        and core.git(controller, "rev-parse", "HEAD").strip() == sha,
        "release controller mismatch",
    )
    run_id, attempt = int(context["GITHUB_RUN_ID"]), int(context["GITHUB_RUN_ATTEMPT"])
    run = api.get("/actions/runs/%s/attempts/%s" % (run_id, attempt))
    actions.identity(run, sha, ".github/workflows/release.yml", "workflow_dispatch")
    proof.require(
        run["id"] == run_id
        and run["run_attempt"] == attempt
        and run["status"] == "in_progress",
        "inactive release run",
    )
    return sha, run_id, attempt


def preflight_snapshot(api, candidate, manifest, artifact_id):
    run = api.get("/actions/runs/%s" % candidate["run_id"])
    actions.identity(
        run, candidate["controller_sha"], actions.WORKFLOW, "workflow_dispatch"
    )
    proof.require(
        run["run_attempt"] == candidate["run_attempt"]
        and run["status"] == "completed"
        and run["conclusion"] == "success",
        "preflight attempt is not completed successful/current",
    )
    for family in actions.FAMILIES:
        refs = [
            r
            for r in run.get("referenced_workflows", [])
            if r["path"].split("@")[0]
            == actions.REPOSITORY
            + "/.github/workflows/release-preflight-%s.yml" % family
        ]
        proof.require(
            len(refs) == 1 and refs[0]["sha"] == candidate["controller_sha"],
            "preflight reusable identity mismatch",
        )
    jobs = actions.producer_jobs(api, candidate)
    artifacts = actions.select_artifacts(api, candidate, jobs)
    all_jobs = api.listing(
        "/actions/runs/%s/attempts/%s/jobs"
        % (candidate["run_id"], candidate["run_attempt"]),
        "jobs",
    )
    collectors = [j for j in all_jobs if j["name"] == "Verify all 14 targets"]
    proof.require(
        len(collectors) == 1
        and collectors[0]["run_id"] == candidate["run_id"]
        and collectors[0]["head_sha"] == candidate["controller_sha"]
        and collectors[0]["status"] == "completed"
        and collectors[0]["conclusion"] == "success",
        "missing successful collector",
    )
    rows = api.listing("/actions/runs/%s/artifacts" % candidate["run_id"], "artifacts")
    final = [
        r
        for r in rows
        if r["id"] == artifact_id
        and r["name"]
        == "preflight-verified-%s-%s" % (candidate["run_id"], candidate["run_attempt"])
    ]
    proof.require(len(final) == 1, "missing final artifact")
    row = final[0]
    wr = row["workflow_run"]
    proof.require(
        wr["id"] == candidate["run_id"]
        and wr["head_sha"] == candidate["controller_sha"]
        and wr["head_branch"] == "main"
        and wr["repository_id"] == wr["head_repository_id"]
        and row["expired"] is False
        and actions.instant(row["expires_at"]) > datetime.now(timezone.utc)
        and actions.instant(collectors[0]["started_at"])
        <= actions.instant(row["created_at"])
        <= actions.instant(collectors[0]["completed_at"]),
        "stale final artifact",
    )
    proof.require(
        manifest["controller"]
        == {
            "run_id": candidate["run_id"],
            "run_attempt": candidate["run_attempt"],
            "source_sha": candidate["source_sha"],
            "controller_sha": candidate["controller_sha"],
            "workflow": actions.WORKFLOW,
        },
        "bundle controller mismatch",
    )
    proof.require(
        actions.main_ci(api, candidate["source_sha"], manifest["main_ci"]["run_id"])
        == manifest["main_ci"],
        "main CI changed",
    )
    for receipt in manifest["artifacts"]:
        target = receipt["target"]
        proof.require(
            receipt["job_id"] == jobs[target]["id"], "producer job receipt mismatch"
        )
        for kind in ("payload", "proof"):
            item = artifacts[(target, kind)]
            proof.require(
                receipt[kind]
                == {
                    **collect.reference(item),
                    **{
                        k: item[k]
                        for k in ("size_in_bytes", "created_at", "expires_at")
                    },
                },
                "producer artifact receipt mismatch",
            )
    proof.require(
        len(manifest["artifacts"]) == len(proof.TARGETS)
        and {r["target"] for r in manifest["artifacts"]} == set(proof.TARGETS),
        "incomplete producer receipts",
    )
    return row, artifacts


def prepare(api, controller, output, artifact_id, bundle_digest, context=None):
    context = os.environ if context is None else context
    sha, run_id, attempt = release_context(controller, context, api)
    proof.require(proof.HEX.fullmatch(bundle_digest), "invalid bundle digest")
    descriptor = api.get(
        "/actions/artifacts/%s" % proof.positive(artifact_id, "final artifact ID")
    )
    output = Path(output)
    proof.require(not output.exists(), "release preparation must be fresh")
    output.mkdir(parents=True)
    archive = output / "bundle.zip"
    api.download(descriptor, archive)
    bundle = output / "bundle"
    extract_bundle(archive, bundle)
    archive.unlink()
    candidate, manifest = bundle_contents(bundle, bundle_digest)
    core.git(
        controller,
        "merge-base",
        "--is-ancestor",
        candidate["source_sha"],
        "origin/main",
    )
    row, artifacts = preflight_snapshot(api, candidate, manifest, artifact_id)
    proof.require(descriptor == row, "final artifact descriptor changed")
    payloads = output / "payloads"
    components, images = [], {}
    for target in proof.TARGETS:
        payload = payloads / target
        artifact = artifacts[(target, "payload")]
        collect.download(api, artifact, payload, output)
        component = collect.producer_evidence(
            candidate, target, payload, bundle / "proofs" / target, artifact
        )
        components.append(component)
        if target.startswith("oci-"):
            image = output / "images" / target
            layout.extract(payload / component["files"][0]["path"], image)
            images[target] = image
    aggregate = proof.aggregate(candidate, components, payloads)
    proof.require(
        aggregate == proof.load(bundle / "components.json")
        and aggregate["digest"] == manifest["aggregate_digest"],
        "aggregate changed",
    )
    index = layout.assemble(candidate, images, output / "oci")
    proof.require(
        index == manifest["oci_index_digest"]
        and collect.inventory(output / "oci") == collect.inventory(bundle / "oci"),
        "assembled OCI bytes changed",
    )
    inventory = canonical.public_inventory(
        candidate, aggregate, bundle, payloads, output / "public"
    )
    canonical.staged_rows(output / "public")
    proof.require(
        preflight_snapshot(api, candidate, manifest, artifact_id) == (row, artifacts),
        "preflight state changed",
    )
    plan = proof.sealed(
        {
            "schema_version": 1,
            "candidate": candidate,
            "bundle_digest": bundle_digest,
            "artifact": {**collect.reference(row), "expires_at": row["expires_at"]},
            "inventory_digest": inventory["digest"],
            "oci_index_digest": index,
            "controller_sha": sha,
            "run_id": run_id,
            "run_attempt": attempt,
        }
    )
    proof.write_new(output / "release-plan.json", plan)
    return plan


def approval_comment(plan):
    return "release %s run %s/%s" % (
        plan["digest"],
        plan["run_id"],
        plan["run_attempt"],
    )


def authorize(api, plan, controller, context=None):
    proof.unseal(plan, PLAN_FIELDS, "release plan")
    proof.validate_candidate(plan["candidate"])
    actual = release_context(
        controller, os.environ if context is None else context, api
    )
    proof.require(
        actual == (plan["controller_sha"], plan["run_id"], plan["run_attempt"]),
        "approval plan is for a different run/controller/attempt",
    )
    reviews = api.get("/actions/runs/%s/approvals" % plan["run_id"])
    matches = [
        r
        for r in reviews
        if r["state"] == "approved"
        and r["user"]["login"] == "Eruhitsuji"
        and r["user"]["type"] == "User"
        and r["comment"] == approval_comment(plan)
        and any(e["name"] == "pypi" for e in r["environments"])
    ]
    proof.require(
        len(matches) == 1,
        "missing explicit Release Authority approval with exact plan/run/attempt comment",
    )
    return {
        "plan_digest": plan["digest"],
        "run_id": plan["run_id"],
        "run_attempt": plan["run_attempt"],
        "reviewer": "Eruhitsuji",
        "environment": "pypi",
    }
