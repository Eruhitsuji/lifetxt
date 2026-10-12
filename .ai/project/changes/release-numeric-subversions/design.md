# Design

Core/tag/runtime versions use three or four numeric components. The missing fourth component is zero. SemVer transport uses numeric +N build metadata, with zero canonicalized to the ordinary version. It is an identity mapping, not an ordering mechanism. Core updates use numeric release components.

Mini build.rs accepts the same 3/4 numeric shape; its binary retains Core identity. The checker verifies Cargo.lock and Cargo.toml mapped values and the complete binary version, never a prefix. Existing native CI also builds a disposable four-part release.

Docker uses exact raw release tags plus numeric major/minor/latest aliases. Desktop config uses SemVer transport. Apple standard metadata remains three-part with the original identity in an additional plist field. This does not implement native subversion update ordering.

No credentials, permissions or dependencies are added. Input is validated before GitHub output emission. Publication and merge require human approval. Native builds and installation remain separately reported checks.
