"""Compressed lifetxt archive codec (`lifetxtz-v1`).

Implements the container and compatibility contract frozen by #692 (see
``docs/en/format-lifetxtz-v1.md``). Reuses the native rendering boundary
(:mod:`lifetxt.native_codec`, #689) for the payload -- no second item
serialization exists in this module.

Dependency-free: only the standard-library ``zipfile``/``json``/``hashlib``
modules are used. Import never calls ``ZipFile.extract()``/``extractall()``;
only the two fixed, literal member names are ever read via ``ZipFile.read()``,
which makes path traversal impossible by construction rather than merely
checked for.
"""

import hashlib
import json
import zipfile
from io import BytesIO

from .atomic import atomic_write_bytes
from .native_codec import items_to_life_text

#: The only container version this codec produces or accepts. See #692.
CONTAINER_VERSION = "lifetxtz-v1"

MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "data.life.txt"

#: Fixed ZIP member metadata for deterministic archive bytes (#692 section 6).
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_FIXED_EXTERNAL_ATTR = 0o600 << 16

#: Decompression resource limits, checked against each member's *declared*
#: (not inflated) size before any decompression -- #692 section 7.
_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_PAYLOAD_BYTES = 256 * 1024 * 1024


class LifetxtzError(ValueError):
    """Raised when a `.lifetxtz` archive does not satisfy the lifetxtz-v1
    contract. Always raised before any destination file is mutated."""


def _manifest_bytes(payload_bytes, item_count, created_at):
    manifest = {
        "container": CONTAINER_VERSION,
        "generator": "lifetxt",
        "created_at": created_at,
        "payload_name": PAYLOAD_NAME,
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "payload_bytes": len(payload_bytes),
        "item_count": item_count,
    }
    text = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return (text + "\n").encode("utf-8")


def _write_member(zip_file, name, data):
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = _FIXED_EXTERNAL_ATTR
    zip_file.writestr(info, data)


def export_lifetxtz(items, output_path, key="id", created_at=None):
    """Write ``items`` as a `.lifetxtz` archive at ``output_path``.

    The payload is the canonicalized native life.txt rendering of ``items``
    via :mod:`lifetxt.native_codec` (#689) -- no second item serialization
    exists in this module. ``created_at`` defaults to the current UTC time;
    tests may inject a fixed value to assert full byte determinism (#692
    section 6). The archive is built entirely in memory and committed to
    ``output_path`` through the shared atomic-replace primitive
    (:func:`lifetxt.atomic.atomic_write_bytes`), so a failure never leaves
    a partial destination.
    """
    if created_at is None:
        import datetime

        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    payload_text = items_to_life_text(items, canonical=True, key=key)
    item_count = len(items)
    payload_bytes = payload_text.encode("utf-8")
    manifest_bytes = _manifest_bytes(payload_bytes, item_count, created_at)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        _write_member(zip_file, MANIFEST_NAME, manifest_bytes)
        _write_member(zip_file, PAYLOAD_NAME, payload_bytes)

    atomic_write_bytes(output_path, buffer.getvalue())


def import_lifetxtz(path):
    """Read a `.lifetxtz` archive at ``path`` and return its validated
    native life.txt payload text.

    Raises :class:`LifetxtzError` for a malformed/foreign ZIP, an
    unexpected member set, a malformed manifest, a container-version
    mismatch, a checksum mismatch, or a declared member size over its
    resource-limit ceiling -- always before decompressing/decoding the
    payload, per #692 sections 3, 5, and 7.
    """
    try:
        zip_file = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise LifetxtzError(
            "'%s' is not a valid .lifetxtz archive: %s" % (path, exc)
        ) from exc

    try:
        names = zip_file.namelist()
        if len(names) != len(set(names)):
            raise LifetxtzError("'%s' contains duplicate archive members." % path)
        if set(names) != {MANIFEST_NAME, PAYLOAD_NAME}:
            raise LifetxtzError(
                "'%s' does not have the exact lifetxtz-v1 member set "
                "{%r, %r}; found %r." % (path, MANIFEST_NAME, PAYLOAD_NAME, names)
            )

        manifest_info = zip_file.getinfo(MANIFEST_NAME)
        if manifest_info.file_size > _MAX_MANIFEST_BYTES:
            raise LifetxtzError(
                "'%s': manifest.json declares %d bytes, exceeding the %d "
                "byte limit; refused before decompressing."
                % (path, manifest_info.file_size, _MAX_MANIFEST_BYTES)
            )
        payload_info = zip_file.getinfo(PAYLOAD_NAME)
        if payload_info.file_size > _MAX_PAYLOAD_BYTES:
            raise LifetxtzError(
                "'%s': data.life.txt declares %d bytes, exceeding the %d "
                "byte limit; refused before decompressing."
                % (path, payload_info.file_size, _MAX_PAYLOAD_BYTES)
            )

        try:
            manifest_bytes = zip_file.read(MANIFEST_NAME)
        except (zipfile.BadZipFile, EOFError, OSError) as exc:
            raise LifetxtzError(
                "'%s': manifest.json could not be decompressed: %s" % (path, exc)
            ) from exc

        try:
            manifest_text = manifest_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LifetxtzError(
                "'%s': manifest.json is not valid UTF-8: %s" % (path, exc)
            ) from exc
        try:
            manifest = json.loads(manifest_text)
        except ValueError as exc:
            raise LifetxtzError(
                "'%s': manifest.json is not valid JSON: %s" % (path, exc)
            ) from exc
        if not isinstance(manifest, dict):
            raise LifetxtzError("'%s': manifest.json must be a JSON object." % path)

        container = manifest.get("container")
        if container != CONTAINER_VERSION:
            raise LifetxtzError(
                "Unsupported lifetxtz container version %r in '%s' (expected "
                "%r). Unknown, older, or newer container versions are "
                "refused rather than guessed." % (container, path, CONTAINER_VERSION)
            )
        if manifest.get("payload_name") != PAYLOAD_NAME:
            raise LifetxtzError(
                "'%s': manifest payload_name %r does not match the required "
                "member name %r." % (path, manifest.get("payload_name"), PAYLOAD_NAME)
            )
        expected_sha256 = manifest.get("payload_sha256")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            raise LifetxtzError("'%s': manifest is missing payload_sha256." % path)

        try:
            payload_bytes = zip_file.read(PAYLOAD_NAME)
        except (zipfile.BadZipFile, EOFError, OSError) as exc:
            raise LifetxtzError(
                "'%s': data.life.txt could not be decompressed: %s" % (path, exc)
            ) from exc
    finally:
        zip_file.close()

    actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise LifetxtzError(
            "'%s': payload checksum mismatch (expected %s, got %s). The "
            "archive is corrupt or was tampered with; refusing to import."
            % (path, expected_sha256, actual_sha256)
        )

    try:
        return payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifetxtzError(
            "'%s': data.life.txt is not valid UTF-8: %s" % (path, exc)
        ) from exc
