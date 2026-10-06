# Confined attachment chunk reads

Linux is the official target for attachment chunk reading. Other operating
systems are unofficial for this feature. The core parser, CLI and other
attachment operations retain their existing platform policies.

The optional helper initially requires Linux x86_64 with glibc, working
`openat2`, trusted procfs and a trusted configured root. Missing prerequisites
make chunk reads unavailable. There is no realpath or legacy-reader fallback.
Linux alone is not a sufficient capability check.

## Explicit installation

From a trusted matching lifetxt source checkout, use a build-time C compiler:

```sh
python scripts/build_attachment_snapshot_helper.py
```

The default installs the executable and integrity manifest beside that
checkout's lifetxt modules. For an installed Python package, pass
`--output /absolute/package/directory/lifetxt/_attachment_snapshot_helper`.
Use the package directory of the interpreter running the server; do not put
the helper in PATH. The source and build script are retained in the source
distribution. No compiler, download or dependency installation runs during a
request. Core pure-Python wheels exclude the host-specific executable and
manifest. Installing the helper does not enable the future restricted consumer.

Keep the package directory, binary and manifest owned by the server user or
root, with no group/world write access. A SHA-256 manifest checks install
consistency; it is not a signature or protection against a malicious owner.
Restart the server after installing, replacing or removing the helper.

## Safety and compatibility

The configured root must be a trusted directory without symlink ancestors.
Root and files must be owned by the server user or root and not group/world
writable. Symlinks at any component, hardlinks, mount crossings below the root,
directories, devices, sockets and pipes are rejected. Ordinary local filesystem
classes ext4, XFS, Btrfs, tmpfs and overlay are admitted by type; network, FUSE
and pseudo filesystems are not. This admission list is not certification of
every deployment: current evidence is Linux x86_64/glibc in an overlay container.
Other actual filesystems, libc/architecture combinations and Python 3.10 hosts
remain unverified. Hostile same-user or privileged writers are outside the trust
model. Current root and declared-file identity must still be revalidated.

Legacy chunk response fields, configured file cap, offset/limit clamping and
optional expected revision retain their meaning. Each chunk comes from one
immutable, size-bounded full snapshot and its full SHA-256. Files that previously
worked through symlinks/hardlinks/mount crossings may now be rejected. Windows,
macOS and helper-free Linux cannot use this chunk feature without an equivalent
verified reader. The change does not disable unrelated attachment operations.

## Cancellation and operations

At most two live workers run per server process, with no queue. A preparation
deadline is at most 30 seconds. A cancelled/timed-out worker retains its slot
until actual exit/reap; a replacement must not be spawned for a stuck worker.
Regular-file kernel I/O can remain uninterruptible after kill. Deadline response
is not a promise of physical cleanup within 30 seconds. If both slots remain
stuck, new reads fail closed and the operator must investigate the filesystem.
Already delivered bytes cannot be revoked. This internal supervisor is not a
principal authorization engine or a new download endpoint.

To disable the helper, stop the server, remove the executable and manifest,
then restart. Chunk reads fail closed. Reverting the code restores previous
reader risks; do not use rollback as an unsafe automatic fallback. No source
data migration or rewrite is involved.
