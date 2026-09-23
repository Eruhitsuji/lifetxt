# lifetxt-mini Phase 0 preservation PoC

This is a deliberately dependency-free Rust spike. It is not a production
runtime or a second life.txt implementation. It reads the checked-in mixed
fixture and changes only the status marker of the supported task `t1`.

## Linux build and run

On a Linux host with Rust installed:

```sh
cd lifetxt-mini
cargo test
cargo build --release
ldd target/release/lifetxt-mini-preservation-poc || true
/usr/bin/time -v target/release/lifetxt-mini-preservation-poc done t1
```

The executable reads `fixtures/mixed-life.txt` relative to the `lifetxt-mini`
working directory. The production design must replace this fixture-only input
with an explicit path/default-file resolver; no such CLI is claimed here.

The crate uses only Rust's standard library. No Python, network, database,
async runtime, or serialization dependency is required at runtime.
