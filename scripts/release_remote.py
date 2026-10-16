"""Explicit read/write adapters. Only the approved release workflow invokes writes."""

import base64
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import release_canonical as canonical
import release_preflight_actions as actions
import release_preflight_proof as proof

IMAGE = "ghcr.io/eruhitsuji/lifetxt"


class TransportError(RuntimeError):
    """Remote state must be rechecked before any bounded retry."""


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        proof.require(
            urllib.parse.urlsplit(newurl).scheme == "https", "redirect requires HTTPS"
        )
        redirected = super().redirect_request(
            request, fp, code, message, headers, newurl
        )
        if (
            urllib.parse.urlsplit(request.full_url).netloc
            != urllib.parse.urlsplit(newurl).netloc
        ):
            redirected.remove_header("Authorization")
        return redirected


def command(*args, input=None):
    try:
        return subprocess.run(
            list(map(str, args)),
            input=input,
            capture_output=True,
            check=True,
            timeout=1800,
        ).stdout
    except subprocess.SubprocessError:
        raise TransportError("remote transport/permission failure") from None


def fetch(url, headers=None, missing=False, limit=2 * 1024**3):
    """HTTPS only, bounded reads; 404 is distinct from auth/network failure."""
    proof.require(urllib.parse.urlsplit(url).scheme == "https", "HTTPS required")
    try:
        with urllib.request.build_opener(SafeRedirect()).open(
            urllib.request.Request(url, headers=headers or {}), timeout=120
        ) as response:
            data = response.read(limit + 1)
            proof.require(len(data) <= limit, "remote response size limit")
            return data
    except urllib.error.HTTPError as exc:
        if missing and exc.code == 404:
            return None
        raise TransportError("remote HTTP status %s" % exc.code) from None


class Remote(actions.Actions):
    def optional(self, path):
        # gh's JSON error/status distinguishes not found from all other failures.
        result = subprocess.run(
            ["gh", "api", self.base + path], capture_output=True, timeout=120
        )
        row = json.loads(result.stdout)
        if result.returncode:
            proof.require(
                str(row.get("status")) == "404",
                "GitHub read failed; no writes permitted",
            )
            return None
        return row

    def mutate(self, path, value):
        return json.loads(
            command(
                "gh",
                "api",
                "--method",
                "POST",
                self.base + path,
                "--input",
                "-",
                input=json.dumps(value).encode(),
            )
            or b"null"
        )

    def patch(self, path, value):
        return json.loads(
            command(
                "gh",
                "api",
                "--method",
                "PATCH",
                self.base + path,
                "--input",
                "-",
                input=json.dumps(value).encode(),
            )
        )

    def array(self, path):
        pages = json.loads(
            command(
                "gh",
                "api",
                "--paginate",
                "--slurp",
                self.base + path + ("&" if "?" in path else "?") + "per_page=100",
            )
        )
        rows = [row for page in pages for row in page]
        proof.require(
            len(rows) == len({r["id"] for r in rows}), "duplicate paginated API row"
        )
        return rows

    def assets(self, release):
        return self.array("/releases/%s/assets" % release["id"])

    def asset_bytes(self, row):
        return command(
            "gh",
            "api",
            "-H",
            "Accept: application/octet-stream",
            self.base + "/releases/assets/%s" % row["id"],
        )

    def tag_source(self, tag):
        row = self.optional("/git/ref/tags/" + tag)
        if row is None:
            return None
        obj = row["object"]
        for _ in range(8):
            if obj["type"] == "commit":
                return obj["sha"]
            proof.require(obj["type"] == "tag", "invalid tag object")
            obj = self.get("/git/tags/" + obj["sha"])["object"]
        raise ValueError("tag chain limit")

    def check_tag(self, candidate):
        version = candidate["version"]
        alternate = "v" + version + ".0" if len(version.split(".")) == 3 else None
        proof.require(
            not alternate or self.tag_source(alternate) is None,
            "equivalent alternate tag already exists",
        )
        current = self.tag_source(candidate["tag"])
        proof.require(
            current in (None, candidate["source_sha"]),
            "tag source conflict; never move tag",
        )
        return current

    def ensure_tag(self, candidate):
        current = self.check_tag(candidate)
        if current is None:
            self.mutate(
                "/git/refs",
                {
                    "ref": "refs/tags/" + candidate["tag"],
                    "sha": candidate["source_sha"],
                },
            )
        proof.require(
            self.tag_source(candidate["tag"]) == candidate["source_sha"],
            "tag not confirmed",
        )

    def release_state(self, plan):
        c = plan["candidate"]
        marker = "lifetxt immutable inventory: " + plan["inventory_digest"]
        release = self.optional("/releases/tags/" + c["tag"])
        if release is not None:
            proof.require(
                release["tag_name"] == c["tag"]
                and not release["draft"]
                and not release["prerelease"]
                and release["body"] == marker,
                "release belongs to a different inventory; correction version required",
            )
        return release

    def ensure_release(self, plan):
        c = plan["candidate"]
        marker = "lifetxt immutable inventory: " + plan["inventory_digest"]
        release = self.release_state(plan)
        if release is None:
            release = self.mutate(
                "/releases",
                {
                    "tag_name": c["tag"],
                    "target_commitish": c["source_sha"],
                    "name": c["tag"],
                    "body": marker,
                    "draft": False,
                    "prerelease": False,
                    "make_latest": "false",
                },
            )
        proof.require(
            release["tag_name"] == c["tag"]
            and not release["draft"]
            and not release["prerelease"]
            and release["body"] == marker,
            "release belongs to a different inventory; correction version required",
        )
        return release

    def upload_missing(self, plan, root, finalize=False):
        release = self.ensure_release(plan)
        expected = canonical.staged_rows(root)
        assets = self.assets(release)
        missing = canonical.remote_inventory(expected, assets, False)
        # Rehash existing downloads; API metadata alone does not authorize reuse.
        by_name = {r["name"]: r for r in expected}
        for asset in assets:
            canonical.bytes_match(self.asset_bytes(asset), by_name[asset["name"]])
        if finalize:
            proof.require(
                set(missing) <= {"SHA256SUMS"}, "primary incomplete; cannot finalize"
            )
        for name in missing:
            if (name == "SHA256SUMS") != finalize:
                continue
            command(
                "gh",
                "release",
                "upload",
                plan["candidate"]["tag"],
                str(Path(root) / name),
                "--repo",
                actions.REPOSITORY,
            )
        canonical.remote_inventory(expected, self.assets(release), finalize)
        return release


class Registry:
    def __init__(self, write=False):
        credential = base64.b64encode(
            (os.environ["GITHUB_ACTOR"] + ":" + os.environ["GH_TOKEN"]).encode()
        ).decode()
        token = json.loads(
            fetch(
                "https://ghcr.io/token?service=ghcr.io&scope=repository:eruhitsuji/lifetxt:"
                + ("pull,push" if write else "pull"),
                {"Authorization": "Basic " + credential},
                limit=1024**2,
            )
        )["token"]
        self.headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json",
        }

    def manifest(self, tag, missing=False):
        proof.require(
            repr(tag) and all(c.isalnum() or c in "_.:-" for c in tag),
            "invalid registry ref",
        )
        return fetch(
            "https://ghcr.io/v2/eruhitsuji/lifetxt/manifests/" + tag,
            self.headers,
            missing,
            16 * 1024**2,
        )

    def blob(self, digest):
        proof.require(
            repr(digest)
            and digest.startswith("sha256:")
            and proof.HEX.fullmatch(digest[7:]),
            "invalid blob digest",
        )
        return fetch(
            "https://ghcr.io/v2/eruhitsuji/lifetxt/blobs/" + digest, self.headers
        )

    def verify(self, plan, root, tag):
        raw = self.manifest(tag)
        proof.require(
            "sha256:" + hashlib.sha256(raw).hexdigest() == plan["oci_index_digest"],
            "registry index mismatch",
        )
        index = json.loads(raw)
        proof.require(
            {
                (r["platform"]["os"], r["platform"]["architecture"])
                for r in index["manifests"]
            }
            == {("linux", "amd64"), ("linux", "arm64")}
            and len(index["manifests"]) == 2,
            "registry platform mismatch",
        )
        manifests = {r["digest"] for r in index["manifests"]}
        for path in sorted((Path(root) / "blobs/sha256").iterdir()):
            digest = "sha256:" + path.name
            data = self.manifest(digest) if digest in manifests else self.blob(digest)
            proof.require(
                hashlib.sha256(data).hexdigest() == path.name
                and len(data) == path.stat().st_size,
                "registry graph bytes mismatch",
            )

    def login(self):
        command(
            "skopeo",
            "login",
            "--username",
            os.environ["GITHUB_ACTOR"],
            "--password-stdin",
            "ghcr.io",
            input=os.environ["GH_TOKEN"].encode(),
        )

    def publish(self, plan, root):
        """Wrap exact index as a named OCI transport entry; no re-encoding."""
        root = Path(root)
        raw = (root / "index.json").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        proof.require(
            "sha256:" + digest == plan["oci_index_digest"], "OCI publish input changed"
        )
        tags = (plan["candidate"]["tag"], plan["candidate"]["version"])
        existing = {tag: self.manifest(tag, missing=True) for tag in tags}
        proof.require(
            all(data is None or data == raw for data in existing.values()),
            "immutable registry tag conflict",
        )
        transport = root.parent / "oci-publish"
        transport.mkdir()
        (transport / "blobs").symlink_to(
            (root / "blobs").resolve(), target_is_directory=True
        )
        (root / "blobs/sha256" / digest).write_bytes(raw)
        (transport / "oci-layout").write_bytes((root / "oci-layout").read_bytes())
        proof.write_new(
            transport / "index.json",
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "mediaType": "application/vnd.oci.image.index.v1+json",
                        "digest": "sha256:" + digest,
                        "size": len(raw),
                        "annotations": {"org.opencontainers.image.ref.name": "release"},
                    }
                ],
            },
        )
        self.login()
        try:
            for tag in tags:
                if existing[tag] is None:
                    command(
                        "skopeo",
                        "copy",
                        "--all",
                        "--preserve-digests",
                        "oci:" + str(transport) + ":release",
                        "docker://" + IMAGE + ":" + tag,
                    )
                proof.require(
                    self.manifest(tag) == raw, "registry publish did not preserve index"
                )
        finally:
            # Keep original layout graph untouched for independent verification.
            (root / "blobs/sha256" / digest).unlink()
        for tag in tags:
            self.verify(plan, root, tag)


def pypi_files(candidate, public, pending=None):
    inventory = proof.load(Path(public) / "release-inventory.json")
    expected = [r for r in inventory["assets"] if r["role"] in ("wheel", "sdist")]
    raw = fetch(
        "https://pypi.org/pypi/lifetxt/"
        + urllib.parse.quote(candidate["version"], safe="")
        + "/json",
        missing=True,
        limit=16 * 1024**2,
    )
    published = [] if raw is None else json.loads(raw)["urls"]
    names = [r["filename"] for r in published]
    proof.require(
        len(names) == len(set(names)) and set(names) <= {r["name"] for r in expected},
        "unexpected PyPI distributions",
    )
    if raw is not None:
        from lifetxt.versioning import canonical_release

        proof.require(
            canonical_release(json.loads(raw)["info"]["version"])
            == candidate["version"],
            "PyPI version mismatch",
        )
    for row in expected:
        matches = [r for r in published if r["filename"] == row["name"]]
        if matches:
            remote = matches[0]
            proof.require(
                remote["digests"]["sha256"] == row["sha256"]
                and remote["size"] == row["bytes"]
                and not remote["yanked"]
                and urllib.parse.urlsplit(remote["url"]).hostname
                == "files.pythonhosted.org",
                "PyPI metadata/hash conflict",
            )
            canonical.bytes_match(fetch(remote["url"]), row)
        else:
            proof.require(pending is not None, "PyPI distribution missing")
            import shutil

            Path(pending).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(public) / row["name"], Path(pending) / row["name"])
    return expected
