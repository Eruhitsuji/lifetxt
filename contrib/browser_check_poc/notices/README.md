# Runtime notice snapshot — incomplete inventory

These are fixed-version upstream licence texts, not a complete distribution
approval. `provenance.json` records original/stored hashes and normalization.
The PoC Core ZIP already contains lifetxt's MIT LICENSE and unmodified sources.

- Pyodide314.0.7: MPL2.0 text and source at
  https://github.com/pyodide/pyodide/tree/314.0.7 .
- CPython3.14.2: its combined history/licence text at
  https://github.com/python/cpython/tree/v3.14.2 .
- Emscripten5.0.3: its MIT/NCSA text at
  https://github.com/emscripten-core/emscripten/tree/5.0.3 .

The pinned Pyodide Makefile.envs identifies Python3.14.2, Emscripten5.0.3 and
link flags for additional libraries (listed in provenance.json). This proves
that top-level npm metadata alone is an insufficient inventory, not that every
flag describes a known exact component version inside the supplied binary.
The installed npm package and python_stdlib.zip contained no standalone licence
or complete third-party notice bundle. The package lock's many available wheels
must not be misrepresented as wheels actually downloaded or shipped by this PoC.

Before any public redistribution, establish the binary's full component/version
inventory, gather the remaining required notices, preserve relevant copyright
statements and decide how recipients obtain corresponding source. Keep an
accurate source-availability notice with the actual subset being distributed.
The Mozilla FAQ's Q7/Q16 distinguish executable/minified forms and source notice
considerations; it does not make these three snapshots a complete approval.
CPython's licence documentation also lists included software notices beyond its
main terms. The Owner must accept a completed, reviewed distribution package.

References checked 2026-10-17:
https://www.mozilla.org/en-US/MPL/2.0/FAQ/
https://docs.python.org/3.14/license.html
https://github.com/pyodide/pyodide/blob/314.0.7/Makefile.envs

No runtime binary is committed or published by this investigation. Keep public
integration blocked on #1358's distribution gate. This is technical inventory
and provenance evidence, not a legal-compliance guarantee.
