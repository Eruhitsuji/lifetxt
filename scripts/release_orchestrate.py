"""Single workflow entry for authenticated, human-approved publication stages."""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import urllib.error
import zipfile
from pathlib import Path

import release_canonical as canonical
import release_channels as channels
import release_plan as plans
import release_preflight_proof as proof
import release_recovery as recovery
import release_remote as remote


class PublishedSourceDefect(ValueError):
    """Actual public native bytes failed their semantic smoke."""


def write_receipt(root, receipt):
    (root / "release-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", newline="\n"
    )


def record_job_failure(root):
    """An external action can fail without returning to this Python entry."""
    path = root / "release-failure.json"
    if path.exists():
        return
    plan_path = root / "release-plan.json"
    plan = proof.load(plan_path) if plan_path.exists() else None
    failed = [
        name
        for name, row in json.loads(os.environ.get("RELEASE_STEPS_JSON", "{}")).items()
        if row.get("outcome") == "failure"
    ]
    receipt = {
        "state": "blocked",
        "stage": "workflow_action",
        "failed_steps": failed,
        "recovery": recovery.classify(
            published=plan is not None, same_bytes=plan is not None
        ),
        "remote_revalidation_required": True,
    }
    if plan:
        receipt.update(
            plan_digest=plan["digest"],
            source_sha=plan["candidate"]["source_sha"],
            version=plan["candidate"]["version"],
        )
    proof.write_new(path, receipt)


def validate_stage(root, controller, api):
    plan = proof.load(root / "release-plan.json")
    plans.authorize(api, plan, controller)
    proof.require(
        not os.environ.get("RELEASE_CRITICAL_BLOCKER"),
        "critical release blocker recorded; human decision required",
    )
    candidate, manifest = plans.bundle_contents(root / "bundle", plan["bundle_digest"])
    proof.require(plan["candidate"] == candidate, "plan candidate mismatch")
    row, _ = plans.preflight_snapshot(api, candidate, manifest, plan["artifact"]["id"])
    proof.require(
        row["digest"] == "sha256:" + plan["artifact"]["sha256"],
        "preflight archive changed",
    )
    inventory = proof.load(root / "public/release-inventory.json")
    proof.require(
        inventory["digest"] == plan["inventory_digest"],
        "plan public inventory mismatch",
    )
    canonical.staged_rows(root / "public")
    channels.no_latest_regression(api, plan)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "start",
            "finalize",
            "verify",
            "downstream",
            "promote",
            "failure",
        ),
    )
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--bundle-digest")
    parser.add_argument("--expected-plan", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args(argv)
    api = remote.Remote()
    root, controller = args.root.resolve(), args.controller.resolve()
    plan = None
    try:
        if args.command == "failure":
            root.mkdir(parents=True, exist_ok=True)
            record_job_failure(root)
            return 0
        if args.command == "prepare":
            plan = plans.prepare(
                api, controller, root, args.artifact_id, args.bundle_digest
            )
            if args.expected_plan:
                proof.require(
                    plan == proof.load(args.expected_plan),
                    "prepared plan changed after approval",
                )
            api.check_tag(plan["candidate"])
            api.release_state(plan)
            channels.no_latest_regression(api, plan)
            summary = (
                "Release plan `%s`\n\nsource `%s` / version `%s` / preflight `%s`\n\nReview the release-plan artifact's public/release-inventory.json and public/SHA256SUMS as well as the plan before approval.\n\nApprove the pypi environment with this exact comment:\n\n```\n%s\n```\n"
                % (
                    plan["digest"],
                    plan["candidate"]["source_sha"],
                    plan["candidate"]["version"],
                    plan["bundle_digest"],
                    plans.approval_comment(plan),
                )
            )
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
                stream.write(summary)
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
                stream.write("source_sha=" + plan["candidate"]["source_sha"] + "\n")
            return 0
        plan = validate_stage(root, controller, api)
        if args.command == "start":
            api.ensure_tag(plan["candidate"])
            # Check existing public state before writing missing GHCR/GitHub bytes.
            release = api.ensure_release(plan)
            canonical.remote_inventory(
                canonical.staged_rows(root / "public"), api.assets(release), False
            )
            remote.pypi_files(
                plan["candidate"], root / "public", root.parent / "dist-pypi"
            )
            remote.Registry(write=True).publish(plan, root / "oci")
            api.upload_missing(plan, root / "public")
            write_receipt(
                root,
                channels.receipt(
                    plan,
                    "partial",
                    {"github": "published", "ghcr": "verified", "pypi": "pending"},
                    "awaiting_pypi",
                ),
            )
            pending = root.parent / "dist-pypi"
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
                stream.write(
                    "pypi_pending=%s\n"
                    % (
                        "true"
                        if pending.exists() and any(pending.iterdir())
                        else "false"
                    )
                )
        elif args.command in ("finalize", "verify"):
            remote.pypi_files(plan["candidate"], root / "public")
            registry = remote.Registry()
            for tag in (plan["candidate"]["tag"], plan["candidate"]["version"]):
                registry.verify(plan, root / "oci", tag)
            if args.command == "finalize":
                api.upload_missing(plan, root / "public", finalize=True)
                write_receipt(
                    root,
                    channels.receipt(
                        plan,
                        "primary_published",
                        dict.fromkeys(("github", "pypi", "ghcr"), "published"),
                        "awaiting_read_only_verification",
                    ),
                )
                return 0
            channels.verify_github(api, plan, root / "public", root / "downloaded")
            proof.require(
                args.source is not None,
                "immutable source checkout required for native conformance",
            )
            import release_preflight_core as core

            core.validate_source(plan["candidate"], args.source)
            try:
                channels.public_smoke(plan, root / "downloaded", args.source)
            except (ValueError, subprocess.SubprocessError):
                raise PublishedSourceDefect(
                    "public native smoke failed; human correction version required"
                ) from None
            write_receipt(
                root,
                channels.receipt(
                    plan,
                    "primary_verified",
                    dict.fromkeys(("github", "pypi", "ghcr", "native"), "verified"),
                    "primary_verified",
                ),
            )
        elif args.command == "downstream":
            receipt = proof.load(root / "release-receipt.json")
            proof.require(
                receipt["plan_digest"] == plan["digest"]
                and receipt["state"] == "primary_verified"
                and all(
                    receipt["channels"].get(k) == "verified"
                    for k in ("github", "pypi", "ghcr", "native")
                ),
                "primary verification required",
            )
            receipt["channels"].update(
                channels.generate(plan, root / "public", root / "generated")
            )
            receipt["state"], receipt["stage"] = (
                "downstream_generated",
                "homebrew_pending",
            )
            receipt["channels"]["homebrew"] = {"state": "blocked"}
            write_receipt(root, receipt)
            receipt["channels"]["homebrew"] = channels.publish_homebrew(
                plan, root / "generated"
            )
            receipt["state"], receipt["stage"] = "verified", "downstream_verified"
            write_receipt(root, receipt)
        else:
            receipt = proof.load(root / "release-receipt.json")
            registry = remote.Registry(write=True)
            registry.verify(plan, root / "oci", plan["candidate"]["tag"])
            remote.pypi_files(plan["candidate"], root / "public")
            release = api.ensure_release(plan)
            canonical.remote_inventory(
                canonical.staged_rows(root / "public"), api.assets(release), True
            )
            # Public readback requires no cross-repository write credential here.
            tap = json.loads(
                remote.command(
                    "gh",
                    "api",
                    "/repos/Eruhitsuji/homebrew-tap/contents/Formula/lifetxt.rb?ref=main",
                )
            )
            import base64

            proof.require(
                base64.b64decode(tap["content"])
                == (root / "generated/lifetxt.rb").read_bytes()
                and tap["sha"] == receipt["channels"]["homebrew"]["blob_sha"],
                "Homebrew changed before promotion",
            )
            channels.promote(api, registry, plan, receipt)
            receipt["state"], receipt["stage"] = "accepted", "latest_promoted"
            write_receipt(root, receipt)
        return 0
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        subprocess.SubprocessError,
        urllib.error.URLError,
        remote.TransportError,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as exc:
        # Avoid stderr, signed URLs, registry credentials or local machine paths.
        error = {
            "state": "blocked",
            "stage": args.command,
            "error_type": type(exc).__name__,
            "recovery": recovery.classify(
                published=args.command != "prepare",
                same_bytes=isinstance(
                    exc, (remote.TransportError, urllib.error.URLError)
                ),
                source_defect=isinstance(exc, PublishedSourceDefect),
                critical=args.command != "prepare"
                and not isinstance(
                    exc,
                    (
                        remote.TransportError,
                        urllib.error.URLError,
                        PublishedSourceDefect,
                    ),
                ),
            ),
            "remote_revalidation_required": True,
        }
        if isinstance(exc, (ValueError, remote.TransportError)):
            # These are validation labels/controlled adapter messages, never
            # raw command stderr or urllib errors containing signed URLs.
            error["reason"] = str(exc)[:240]
        if plan:
            error.update(
                plan_digest=plan["digest"],
                version=plan["candidate"]["version"],
                source_sha=plan["candidate"]["source_sha"],
            )
        root.mkdir(parents=True, exist_ok=True)
        (root / "release-failure.json").write_text(
            json.dumps(error, indent=2) + "\n", newline="\n"
        )
        parser.exit(
            1,
            "release stopped at %s (%s); inspect sanitized failure receipt and remote state before retry\n"
            % (args.command, type(exc).__name__),
        )


if __name__ == "__main__":
    sys.exit(main())
