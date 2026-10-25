# Rebuild evidence and identity boundary

Owner requested continuation of #1415/#1417. Source main 32dc60b9;
branch ops/1415-rebuild-verification; final PR base main. Operations/High,
W-model, M score6 for one source/compiler/candidate/retention evidence chain.
Owner/Merge Eruhitsuji, Implementer Codex; separate review pending.

The original build tree/runtime were unavailable. Reused locked upstream sources
and the existing curation/staging recipe, obtained host Python3.14.2 and fixed
emsdk5.0.3, applied the five pinned SDK patches, compared struct_info and compiler
records. Clang bytes and Emscripten revision exactly match the old receipt.
Host prerequisites were provided locally using hash-checked official Ubuntu
packages with recorded prefix relocation and CMake3.31.6. No system privilege
escalation or upstream runtime/source change was made.

After earlier failed/incomplete attempts, make attempt3 returned exit0 with
complete captured output. Latest verifier and actual Node/WASM probes bind the
same five rebuilt runtime hashes. Source manifests (CPython3204, Pyodide202 and
five dependencies798 C/header files) match the original retained source checks.
A fresh 68-file staging manifest is preserved in source-build-proof.json.

Three of five runtime files differ from the old fixed candidate. Raw probe
profile names refer to the source recipe lifetxt-hkscs-free-1; they must NOT be
used to replace live profiles/hkscs-free-1 records. candidate.json explicitly
identifies the new unadopted candidate and false distribution state. The old
custom_distribution.check_runtime rejects it, as required. No new live profile,
lock change or final checker build is included.

A private recovery checkpoint retains candidate, regular build/source/object/
installed-library files, curated input, provenance and raw evidence. SDK binaries,
node_modules, Git internals and Python caches are excluded and documented. All
10924 restored payloads and a re-executed complete source/object report were
verified. The archive is retained privately; only filename/size/hash and results
are public, never a private file URL or workspace path. It is not a legally
accepted complete public source/binary distribution. SDK reacquisition and the
exact llvm-ar hash check are required for the reverify script; a different-prefix
incremental make is not promised.

Viewpoints: source/binary identity, receipt binding, source/object limits,
retention/restore, bounded browser acceptance, fail-closed and independent review.
Rollback: human-reviewed revert of this evidence-only PR. No deployment.
