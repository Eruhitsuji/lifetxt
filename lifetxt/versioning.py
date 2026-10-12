"""Release numbering: X.Y.Z, with an optional numeric subversion."""

import re

_RELEASE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2,3}")


def release_parts(version):
    """Return four numeric components; the omitted subversion is zero."""
    if not isinstance(version, str) or not _RELEASE.fullmatch(version):
        raise ValueError("release version must be X.Y.Z or X.Y.Z.N: %r" % version)
    parts = tuple(int(part) for part in version.split("."))
    return parts if len(parts) == 4 else parts + (0,)


def canonical_release(version):
    parts = release_parts(version)
    return ".".join(str(part) for part in (parts if parts[3] else parts[:3]))


def semver_metadata(version):
    """Encode a subversion as numeric build metadata, not a prerelease.

    SemVer ignores build metadata for ordering. Release/update comparisons
    must use release_parts(), never this transport representation.
    """
    parts = release_parts(version)
    base = ".".join(str(part) for part in parts[:3])
    return base + ("+%d" % parts[3] if parts[3] else "")
