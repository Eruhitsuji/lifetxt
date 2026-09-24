# lifetxt-mini distribution

lifetxt-mini is the Python-free, standalone strict-subset runtime for small or
offline Linux systems. Python lifetxt remains the full/reference
implementation; both use the same life.txt format and Mini never defines a
second persisted format.

Official release artifacts are published on the GitHub Release for the matching
lifetxt tag:

| Architecture | Artifact |
| --- | --- |
| Linux x86_64 (Intel/AMD 64-bit) | lifetxt-mini-vX.Y.Z-linux-x86_64 |
| Linux AArch64 (64-bit ARM) | lifetxt-mini-vX.Y.Z-linux-aarch64 |

Choose with uname -m: x86_64 selects the first artifact and aarch64 or arm64
selects the second. The artifacts are static musl-oriented binaries; the
release workflow tests each binary on its native architecture before
publication.

After downloading the matching binary and its .sha256 file from the GitHub
Release, verify it with sha256sum -c, run lifetxt-mini --help, and optionally
install it with sudo install -m 0755 into /usr/local/bin.

The released command surface is list, show, Mini-profile check, add, done, and
deterministic today --date YYYY-MM-DD. Mini intentionally omits the Python
implementation's broader recurrence, timezone, dependency, priority, Web, and
integration features. Windows, macOS, ARMv7, RISC-V, Android/iOS, and
bare-metal targets are not official Mini release targets.

The Mini artifact version is the repository release tag (vX.Y.Z); it is not an
independent product version. A release is published only from the tagged
revision after native architecture, static linkage, conformance, checksum, and
smoke checks pass.

The version printed by lifetxt-mini --version is injected from the same
pyproject.toml project.version used by the Core CLI and release tag checks.
Matching versions identify one repository release, not feature parity: Python
Core remains broader than the Mini Runtime Profile.
