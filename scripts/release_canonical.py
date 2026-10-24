"""One immutable public inventory and LF checksum manifest; no network writes."""

import hashlib
import re
import shutil
from pathlib import Path

import release_preflight_desktop as desktop
import release_preflight_proof as proof


def github_asset_name(name):
    """Choose a stable ASCII name before GitHub can rewrite upload names."""
    desktop.public_name(name)
    name = name.replace(" ", ".")
    proof.require(
        re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._+-]*", name) is not None,
        "unsupported public asset name",
    )
    return name


def checksum_bytes(rows):
    names = [row["name"] for row in rows]
    proof.require(
        len(names) == len(set(n.casefold() for n in names)), "duplicate public name"
    )
    for row in rows:
        desktop.public_name(row["name"])
        proof.require(not row["name"].startswith("-"), "option-like public name")
        proof.require(proof.HEX.fullmatch(row["sha256"]), "invalid public hash")
    return "".join(
        "%s  %s\n" % (r["sha256"], r["name"])
        for r in sorted(rows, key=lambda r: r["name"])
    ).encode()


def validate_checksums(raw, rows):
    proof.require(
        b"\r" not in raw and raw == checksum_bytes(rows),
        "noncanonical/missing/extra checksum entries",
    )


def public_inventory(candidate, aggregate, bundle, payloads, output):
    """Exclude private bundled Core and OCI archives; retain Mini sidecars/notes.

    The inventory covers payloads; SHA256SUMS covers those plus the inventory,
    excluding only SHA256SUMS itself. No component can finalize independently.
    """
    proof.require(
        aggregate == proof.aggregate(candidate, aggregate["components"], payloads),
        "aggregate mismatch",
    )
    output = Path(output)
    proof.require(not output.exists(), "canonical staging must be fresh")
    output.mkdir(parents=True)
    entries, aliases = {}, {}
    for component in aggregate["components"]:
        target = component["target"]
        family = target.split("-", 1)[0]
        mapping = {}
        if family == "desktop":
            report = proof.load(
                Path(bundle) / "proofs" / target / "desktop-bundle-report.json"
            )
            mapping = {r["path"]: r["public_name"] for r in report["installers"]}
        for row in component["files"]:
            if (
                family == "oci"
                or row["role"] == "bundled-core"
                or (family == "standalone" and row["role"] == "checksum")
            ):
                continue
            name = github_asset_name(mapping.get(row["path"], row["path"]))
            desktop.public_name(name)
            proof.require(
                "/" not in name
                and name not in {"SHA256SUMS", "release-inventory.json"},
                "reserved public name",
            )
            entry = {
                "name": name,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "role": row["role"],
                "targets": [target],
            }
            if name.casefold() in aliases:
                previous = entries[aliases[name.casefold()]]
                proof.require(
                    name == previous["name"]
                    and family == "mini"
                    and row["role"] == "notes"
                    and all(
                        entry[k] == previous[k] for k in ("sha256", "bytes", "role")
                    ),
                    "conflicting public name",
                )
                previous["targets"].append(target)
            else:
                aliases[name.casefold()] = name
                entries[name] = entry
                shutil.copyfile(
                    proof.payload_path(Path(payloads) / target, row["path"]),
                    output / name,
                )
    inventory = proof.sealed(
        {
            "schema_version": 1,
            "source_sha": candidate["source_sha"],
            "version": candidate["version"],
            "candidate_digest": candidate["digest"],
            "assets": sorted(entries.values(), key=lambda r: r["name"]),
        }
    )
    proof.write_new(output / "release-inventory.json", inventory)
    rows = inventory["assets"] + [
        {
            "name": "release-inventory.json",
            "sha256": proof.file_digest(output / "release-inventory.json"),
            "bytes": (output / "release-inventory.json").stat().st_size,
        }
    ]
    (output / "SHA256SUMS").write_bytes(checksum_bytes(rows))
    return inventory


def staged_rows(root):
    root = Path(root)
    inventory = proof.load(root / "release-inventory.json")
    proof.unseal(
        inventory,
        {"schema_version", "source_sha", "version", "candidate_digest", "assets"},
        "public inventory",
    )
    rows = list(inventory["assets"])
    rows.append(
        {
            "name": "release-inventory.json",
            "sha256": proof.file_digest(root / "release-inventory.json"),
            "bytes": (root / "release-inventory.json").stat().st_size,
        }
    )
    validate_checksums((root / "SHA256SUMS").read_bytes(), rows)
    rows.append(
        {
            "name": "SHA256SUMS",
            "sha256": proof.file_digest(root / "SHA256SUMS"),
            "bytes": (root / "SHA256SUMS").stat().st_size,
        }
    )
    proof.require(
        {p.name for p in root.iterdir()} == {r["name"] for r in rows},
        "public staging inventory mismatch",
    )
    for row in rows:
        path = root / row["name"]
        proof.require(
            not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and proof.file_digest(path) == row["sha256"],
            "staged bytes mismatch",
        )
    return rows


def remote_inventory(expected, actual, complete):
    """Validate before any write. A missing item is retryable; a conflict is not."""
    want = {r["name"]: r for r in expected}
    names = [r["name"] for r in actual]
    proof.require(
        len(names) == len(set(n.casefold() for n in names)),
        "duplicate remote public name",
    )
    proof.require(set(names) <= set(want), "unexpected remote public asset")
    for row in actual:
        proof.require(
            row["size"] == want[row["name"]]["bytes"]
            and row["digest"] == "sha256:" + want[row["name"]]["sha256"],
            "published bytes conflict; correction version required",
        )
    proof.require(
        not complete or set(names) == set(want), "incomplete public inventory"
    )
    return sorted(set(want) - set(names))


def bytes_match(raw, row):
    proof.require(
        len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"],
        "downloaded public bytes mismatch",
    )


def parse_checksums(raw):
    proof.require(b"\r" not in raw and raw.endswith(b"\n"), "checksum newline mismatch")
    rows = []
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        proof.require(match is not None, "invalid checksum entry")
        rows.append({"name": match[2], "sha256": match[1]})
    validate_checksums(raw, rows)
    return {r["name"]: r["sha256"] for r in rows}
