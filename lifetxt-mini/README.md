# lifetxt-mini Phase 1

`lifetxt-mini` is a dependency-free, read-only Rust runtime for the Mini-1
profile. Python Core remains the full/reference implementation. The runtime
never writes `life.txt` and keeps unsupported records opaque.

```sh
cargo run -- list path/to/life.txt
cargo run -- show --id=t1 path/to/life.txt
cargo run -- check path/to/life.txt
```

Input resolution is an explicit path, then `LIFETXT_FILE`, then `./life.txt`.
`show` requires an exact `--id=` selector; missing or duplicate IDs fail. The
Mini profile supports `[ ]`, `[x]`, `[N]` with record types `T`, `E`, and `N`,
quoted UTF-8 titles, and details such as `id`, `due`, `on`, `from`, `to`,
`project`, and `tag`. Unknown details are retained in the source-backed record
and unsupported Full Format records are skipped by `check` rather than being
presented as Mini semantics.

Core-style options not implemented by Mini are rejected. Output identifies the
Mini Runtime Profile where semantics differ. Linux x86_64 and AArch64 are the
official supported targets; static musl builds are verified in CI.

## Phase 2 mutation

The done --id=<id> path completes an exact, open Mini Task by replacing only
its [ ] status marker with [x]. The add "title" path appends a Mini record and
accepts --type task|event|note plus --id, --due, --on, --from, --to, --project,
and --tag. Mutation refuses duplicate IDs, unsupported targets, invalid UTF-8,
and symbolic-link paths.

Writes use a sibling temporary file, flush the file, preserve the source mode
on Unix, then atomically replace the original and sync its containing
directory. Before replacement, the source bytes are read again; a concurrent
change aborts without replacing the authoritative file. Failed writes remove
the temporary file where possible. The operation does not canonicalize or
rewrite unrelated source bytes.
