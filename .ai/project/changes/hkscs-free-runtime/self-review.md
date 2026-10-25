# Informational self-review

Implementer: Codex; Operations/High. This is not independent review or authority
verification. Final PR head is bound in the PR comment after upload.

Reviewed source filtering, source-specific provenance, build inputs, object/data
inclusion, codec behavior, failure handling, generated output bytes, canonical
metadata, fixture compatibility, Worker/browser isolation and approval boundaries.
No managed standards, Core/CLI behavior, current public distribution binding or
publication gate has been weakened. Both actual flags remain false.

Resolved findings:

1. The initial manual bootstrap excluded five files. HK-only tests were also
   identified; the final staged profile excludes all seven. The final source
   verifier caught the two tests still present in the developer source; those
   unused tests were removed before the final passing source proof. They were
   excluded from the runtime stdlib throughout.
2. The initial make returned zero but its stdlib ZIP lacked a central directory;
   actual WASM startup rejected it. Re-generation and complete CRC checking
   exposed the failure. The staged build now writes a sorted, fixed-metadata ZIP
   from BytesIO in one write, with validity checked before publication to disk.
3. Incremental shell append generation duplicated the embedded JS body and
   failed Acorn parsing. A single-write generation helper replaces that recipe,
   is a Makefile prerequisite, and is bound to the build profile. The corrected
   embed has one initializer and the final make/probes pass. Unit tests cover
   overwriting old output and ZIP stability after changing source timestamps.

Host setup adaptations are explicit: SDK Node22 SIGSEGV was replaced with the
existing Node24 executable; SDK tar ownership is ignored; serial compileall
avoids prohibited AF_UNIX sockets. Initial/failed commands and final results are
retained in compressed sanitized logs. Very long generated JS/command lines are
represented by their original line SHA256 to avoid shipping runtime source in
an exception dump; complete local originals were retained. No failing test suite
was discarded or reported as passed.

Evidence limits: source/objects/runtime checks prove this candidate's bounded
removal behavior, not independent compiler attestation, full legal sufficiency,
cross-host bit reproducibility or public distribution approval. Runtime/source
archives containing other still-reviewed material are retained locally, not
uploaded as public PR binaries. The current website builder is unchanged; its
replacement needs a reviewed custom provenance/distribution contract in #1398.

Final independent implementation/integration review and human merge/publication
boundaries remain required. No external permission email, merge or deploy occurs.
