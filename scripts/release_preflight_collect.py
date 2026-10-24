"""Read-only full-target preflight controller. Never authorizes publication."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import release_preflight_actions as actions
import release_preflight_core as core
import release_preflight_desktop as desktop
import release_preflight_editor as editor
import release_preflight_mini as mini
import release_preflight_oci as oci
import release_preflight_oci_layout as layout
import release_preflight_proof as proof
import release_preflight_standalone as standalone

PRODUCERS = {
    "core": core,
    "standalone": standalone,
    "desktop": desktop,
    "mini": mini,
    "oci": oci,
    "editor": editor,
}


def trusted_context(candidate, controller, context):
    core.validate_context(candidate, controller, context)
    proof.require(
        candidate["repository"] == actions.REPOSITORY, "untrusted preflight repository"
    )
    proof.require(
        context.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and context.get("GITHUB_REF") == "refs/heads/main",
        "preflight requires a manual main run",
    )
    proof.require(
        context.get("GITHUB_WORKFLOW_REF")
        == actions.REPOSITORY + "/" + actions.WORKFLOW + "@refs/heads/main"
        and context.get("GITHUB_WORKFLOW_SHA") == candidate["controller_sha"]
        and context.get("GITHUB_SHA") == candidate["controller_sha"],
        "untrusted controller workflow/ref",
    )
    # Full checkout history establishes source reachability without mutable ref resolution.
    core.git(
        controller,
        "merge-base",
        "--is-ancestor",
        candidate["source_sha"],
        "origin/main",
    )


def prepare(
    source_sha, version, main_ci_run_id, controller, output, github_output, context, api
):
    candidate = proof.candidate(
        actions.REPOSITORY,
        version,
        source_sha,
        context["GITHUB_WORKFLOW_SHA"],
        int(context["GITHUB_RUN_ID"]),
        int(context["GITHUB_RUN_ATTEMPT"]),
    )
    trusted_context(candidate, controller, context)
    ci = actions.main_ci(api, source_sha, main_ci_run_id)
    proof.write_new(output, candidate)
    # Values are generated JSON/hex, never unvalidated input in output commands.
    with Path(github_output).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "candidate_json=" + json.dumps(candidate, separators=(",", ":")) + "\n"
        )
        stream.write("main_ci_json=" + json.dumps(ci, separators=(",", ":")) + "\n")
    return candidate


def reference(row):
    return {"id": row["id"], "name": row["name"], "sha256": row["digest"][7:]}


def download(api, row, destination, temporary):
    archive = temporary / (str(row["id"]) + ".zip")
    api.download(row, archive)
    actions.extract_zip(archive, destination)
    archive.unlink()  # Disposable verified transport ZIP only; payload remains.


def producer_evidence(candidate, target, payload, reports, artifact):
    family = target.split("-", 1)[0]
    component_name = family + "-component.json"
    report_name = family + (
        "-bundle-report.json" if family == "desktop" else "-build-report.json"
    )
    expected = {"candidate.json", component_name, report_name}
    if family == "desktop":
        expected.add("desktop-stage.json")
    proof.require(
        {p.name for p in reports.iterdir()} == expected,
        "producer proof inventory mismatch",
    )
    for name in expected:
        path = proof.payload_path(reports, name)
        proof.require(path.stat().st_size <= 4 * 1024**2, "producer report size limit")
    proof.require(
        proof.load(reports / "candidate.json") == candidate,
        "producer candidate mismatch",
    )
    report = proof.load(reports / report_name)
    component = proof.load(reports / component_name)
    if family == "core":
        rebuilt = core.finish(candidate, report, payload, reference(artifact))
    else:
        rebuilt = PRODUCERS[family].finish(
            candidate, report, payload, reference(artifact), target
        )
    proof.require(component == rebuilt, "component/report/API reference mismatch")
    if family == "desktop":
        stage = proof.load(reports / "desktop-stage.json")
        proof.unseal(stage, desktop.STAGE_FIELDS, "Desktop stage")
        proof.require(
            all(
                report[key] == stage[key]
                for key in desktop.STAGE_FIELDS - {"toolchain"}
            )
            and all(
                report["toolchain"].get(key) == value
                for key, value in stage["toolchain"].items()
            ),
            "Desktop stage/bundle mismatch",
        )
    return component


def require_dependencies(needs):
    proof.fields(needs, {"prepare", *actions.FAMILIES}, "preflight dependencies")
    proof.require(
        all(row.get("result") == "success" for row in needs.values()),
        "preflight dependency failed/skipped/cancelled",
    )


def inventory(root):
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        proof.payload_path(root, relative)
        result.append(
            {
                "path": relative,
                "sha256": proof.file_digest(path),
                "bytes": path.stat().st_size,
            }
        )
    return result


def collect(candidate, ci, controller, output, needs, context, api):
    trusted_context(candidate, controller, context)
    require_dependencies(needs)
    proof.require(
        actions.main_ci(api, candidate["source_sha"], ci["run_id"]) == ci,
        "main CI evidence changed",
    )
    run = actions.current_run(api, candidate)
    jobs = actions.producer_jobs(api, candidate)
    artifacts = actions.select_artifacts(api, candidate, jobs)
    output = Path(output)
    proof.require(
        not output.exists() and not output.is_symlink(),
        "proof bundle output must be fresh",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Failure leaves diagnostics but cannot leave a success manifest at output.
    with tempfile.TemporaryDirectory(
        prefix="lifetxt-preflight-collect-", dir=output.parent
    ) as temporary:
        work = Path(temporary)
        bundle, payloads = work / "bundle", work / "payloads"
        bundle.mkdir()
        components, receipts, images = [], [], {}
        for target in proof.TARGETS:
            artifact, proof_artifact = [
                artifacts[(target, kind)] for kind in ("payload", "proof")
            ]
            payload, reports = payloads / target, bundle / "proofs" / target
            download(api, artifact, payload, work)
            download(api, proof_artifact, reports, work)
            component = producer_evidence(candidate, target, payload, reports, artifact)
            components.append(component)
            receipts.append(
                {
                    "target": target,
                    "job_id": jobs[target]["id"],
                    **{
                        kind: {
                            **reference(artifacts[(target, kind)]),
                            "size_in_bytes": artifacts[(target, kind)]["size_in_bytes"],
                            "created_at": artifacts[(target, kind)]["created_at"],
                            "expires_at": artifacts[(target, kind)]["expires_at"],
                        }
                        for kind in ("payload", "proof")
                    },
                }
            )
            if target.startswith("oci-"):
                image = work / target
                layout.extract(payload / component["files"][0]["path"], image)
                graph = layout.validate(image, candidate, target)
                proof.require(
                    graph["manifest_digest"] == component["oci_digest"],
                    "OCI component/manifest mismatch",
                )
                images[target] = image
        aggregate = proof.aggregate(candidate, components, payloads)
        index_digest = layout.assemble(candidate, images, bundle / "oci")
        proof.write_new(bundle / "candidate.json", candidate)
        proof.write_new(bundle / "components.json", aggregate)
        # Re-fetch mutable API state after downloads/assembly; expiry or a new
        # attempt must not be hidden by the earlier successful API snapshot.
        actions.current_run(api, candidate)
        final_jobs = actions.producer_jobs(api, candidate)
        proof.require(
            final_jobs == jobs
            and actions.select_artifacts(api, candidate, final_jobs) == artifacts,
            "Actions evidence changed during collection",
        )
        proof.require(
            actions.main_ci(api, candidate["source_sha"], ci["run_id"]) == ci,
            "main CI changed during collection",
        )
        trusted_context(candidate, controller, context)
        manifest = proof.sealed(
            {
                "schema_version": 1,
                "candidate_digest": candidate["digest"],
                "status": "preflight_verified",
                "publication_authorized": False,
                "aggregate_digest": aggregate["digest"],
                "main_ci": ci,
                "controller": {
                    "run_id": run["id"],
                    "run_attempt": run["run_attempt"],
                    "source_sha": candidate["source_sha"],
                    "controller_sha": run["head_sha"],
                    "workflow": run["path"],
                },
                "artifacts": receipts,
                "oci_index_digest": index_digest,
                "files": inventory(bundle),
            }
        )
        proof.write_new(bundle / "preflight-bundle.json", manifest)
        bundle.rename(output)  # Same filesystem: expose success bundle atomically.
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("prepare")
    for name in ("source-sha", "version", "main-ci-run-id", "github-output"):
        create.add_argument(
            "--" + name, required=True, type=int if name == "main-ci-run-id" else str
        )
    combine = sub.add_parser("collect")
    for name in ("candidate", "main-ci", "needs"):
        combine.add_argument("--" + name, required=True, type=Path)
    for command in (create, combine):
        command.add_argument("--controller", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        api = actions.Actions()
        if args.command == "prepare":
            prepare(
                args.source_sha,
                args.version,
                args.main_ci_run_id,
                args.controller,
                args.output,
                args.github_output,
                os.environ,
                api,
            )
        else:
            collect(
                proof.load(args.candidate),
                proof.load(args.main_ci),
                args.controller,
                args.output,
                proof.load(args.needs),
                os.environ,
                api,
            )
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as exc:
        # gh stderr may contain signed artifact URLs: do not propagate it.
        parser.exit(
            1,
            "preflight collection rejected: %s\n"
            % (
                type(exc).__name__
                if isinstance(exc, subprocess.SubprocessError)
                else exc
            ),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
