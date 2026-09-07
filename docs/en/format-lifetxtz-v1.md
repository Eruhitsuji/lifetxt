# Compressed Lifetxt Archive Format (`lifetxtz-v1`)

Status: **approved for implementation** (#692). Implemented by #693.

This document defines the container and compatibility contract for the
`.lifetxtz` compressed native archive format. It is a specification only;
#693 implements it unmodified. Any future container change requires a new
document version (`lifetxtz-v2`) and an explicit refusal/migration plan.

## 1. Purpose and role

`.lifetxtz` is a **compact, portable storage/transfer** container for a
lifetxt payload -- the equivalent of "zip a life.txt for email/backup", with
integrity verification built in. It is **not**:

- an authoritative live-edit format (plain `life.txt` remains authoritative);
- a multi-file workspace bundle, attachment archive, or config/history
  package (v1 carries exactly one native payload and nothing else);
- an encrypted container (no password protection in v1 -- see §9).

## 2. Container technology

A standard ZIP archive (stdlib `zipfile`, `ZIP_DEFLATED` compression), no
external dependency and no custom compression algorithm.

## 3. Member layout

Exactly two members, in this fixed order, and no others:

```text
example.lifetxtz
├── manifest.json
└── data.life.txt
```

- `data.life.txt` is the payload: the canonicalized native lifetxt text
  produced by `lifetxt.native_codec.items_to_life_text(items, canonical=True)`
  (#689) -- the same rendering `export --format life --canonical` produces
  -- UTF-8 encoded, no BOM.
- `manifest.json` identifies and verifies the archive (§4).

Import requires the member set to be **exactly**
`{"manifest.json", "data.life.txt"}`; anything else -- a missing member, an
extra member, a duplicate name, a member under a subdirectory -- is refused
before any bytes are extracted or written anywhere. This is also the path-
traversal defense: since only these two literal, non-path names are ever
read (via `ZipFile.read(name)`, never `extract()`/`extractall()`), a
crafted archive cannot cause a write to any path outside memory, let alone
outside the destination the caller explicitly names.

## 4. Manifest

```json
{
  "container": "lifetxtz-v1",
  "generator": "lifetxt",
  "created_at": "2026-09-07T12:00:00+00:00",
  "payload_name": "data.life.txt",
  "payload_sha256": "<64 lowercase hex characters>",
  "payload_bytes": 128,
  "item_count": 3
}
```

| Field | Required | Meaning |
|---|---|---|
| `container` | yes | Must be exactly `"lifetxtz-v1"`. |
| `generator` | yes | Producer identity; informational. |
| `created_at` | yes | UTC ISO-8601 export timestamp; provenance, not deterministic (§6). |
| `payload_name` | yes | Must be exactly `"data.life.txt"`, matching the member name. |
| `payload_sha256` | yes | SHA-256 of `data.life.txt`'s UTF-8 bytes, lowercase hex. |
| `payload_bytes` | yes | `len()` of those same UTF-8 bytes. |
| `item_count` | yes | Number of items encoded in the payload; informational cross-check. |

Serialized as `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"`,
UTF-8 encoded.

## 5. Integrity verification

Import always, unconditionally:

1. Decodes `manifest.json` as UTF-8 JSON. A decode/parse failure is refused.
2. Confirms `container == "lifetxtz-v1"` (refuses a foreign ZIP or an
   unsupported/newer/older container version -- v1 has no predecessor, so
   any other value is refused by name, not guessed at).
3. Confirms every required manifest field above is present and of the
   expected type.
4. Confirms `payload_name == "data.life.txt"`.
5. Computes SHA-256 over the actual extracted `data.life.txt` bytes and
   compares it to `payload_sha256`. A mismatch (corruption, tampering, or a
   manifest/payload produced by different runs) is refused.
6. Only after all of the above succeeds are the payload bytes decoded as
   UTF-8 and handed to the authoritative parser (`lifetxt.parser.parse_text`)
   for the normal syntax-validation-before-write path every other import
   preset already uses.

Every refusal happens **before** any destination file is touched, matching
#690's identical discipline for the SQLite codec.

## 6. Determinism

Given the **same filtered item set and export options**:

- `data.life.txt`'s bytes are byte-identical across runs (canonical
  rendering of an already-deterministic in-memory structure -- see #689);
- `payload_sha256`/`payload_bytes`/`item_count` are therefore also
  byte-identical (they are pure functions of the payload);
- `manifest.json`'s field *order* is deterministic (`sort_keys=True`); its
  serialized bytes are fully deterministic **except** for `created_at`,
  which is provenance (when the export ran), not payload fidelity -- the
  same distinction #690 draws for SQLite's `metadata.exported_at`;
- ZIP member metadata is normalized for determinism: every `ZipInfo` uses a
  fixed `date_time` (`(1980, 1, 1, 0, 0, 0)`, the ZIP epoch minimum) and a
  fixed `external_attr` (`0o600 << 16`, owner read/write, no
  execute/setuid bits, matching this project's existing private-evidence
  file-permission convention), members are written in the fixed order
  `manifest.json` then `data.life.txt`, and no ZIP "extra field" data is
  set.

**Net claim**: two exports of the same logical input produce byte-identical
`.lifetxtz` files if and only if `created_at` is held equal between them
(e.g. injected by a test, or two exports within the same wall-clock
second are not promised identical either, since `created_at` still
differs). This is the honest, testable contract #692 asks for -- stronger
than SQLite's contract (§4 of the SQLite spec explicitly does *not* promise
file-byte determinism at all), because a ZIP file's on-disk bytes are
fully within this codec's control, unlike SQLite's own B-tree page layout.

## 7. Resource limits (decompression safety)

Before decompressing any member, its **declared** uncompressed size
(`ZipInfo.file_size`, read from the central directory, never inflated
data) is checked against a bounded ceiling:

| Member | Ceiling | Rationale |
|---|---|---|
| `manifest.json` | 64 KiB | The manifest has a small, fixed field set; never legitimately larger. |
| `data.life.txt` | 256 MiB | Generous headroom over any realistic life.txt payload while still bounding a zip-bomb's worst case. |

A member whose declared size exceeds its ceiling is refused **without
decompressing it**, so a maliciously crafted archive cannot force
unbounded memory allocation regardless of its compression ratio. The
member-count/name check in §3 additionally bounds the archive to exactly
two members, so there is no "many small members" amplification vector
either.

## 8. Extension recognition

`lifetxt import` infers `--preset lifetxtz` for the `.lifetxtz` extension
only (case-insensitive), matching #689's "never guess a plain `.txt`"
precedent.

## 9. Future evolution

Not in v1, and explicitly out of scope until real evidence justifies a new
version:

- password protection / encryption;
- attachments, config, workspace history, or any file beyond one native
  payload;
- multi-file workspace bundles;
- random-access / query-accelerated internal indexing;
- zstd/lz4/msgpack or any other new runtime dependency.
