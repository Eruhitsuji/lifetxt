# Informational self-review

Checked source recipe versus fixed distribution identity, immutable old pins,
actual probe hash binding, source/object coverage, failed build retention,
private archive restoration, public path sanitization and publication boundaries.

Host setup: apt failed setgroups; used local package extraction rather than
privilege changes. SDK extraction required no-same-owner. SDK ccache initially
could not find CMake; set the tool PATH and used CMake3.31.6 as required by the
upstream cmake<4 requirement. The first make failed missing LT_SYS_SYMBOL_USCORE;
added the official libltdl-dev host macro package. The second make reported exit2
with an incomplete streamed log; no success was inferred. The third attempt
captured complete subprocess output and returned exit0. This was an incremental
recovery of the new staged tree, not an asserted single-pass reproducible build.

Python Playwright1.55.1 was unavailable (npm and Python versions differ); installed
1.55.0 and then ran the existing probe using fixed Chrome153. Both the missing
Python-module attempt and the successful actual probe remain local evidence;
only the successful measured result is counted, with its actual scope.

Three runtime files differ from old records; do not rewrite profiles, relabel
bytes, or patch the auditor to accept them. Raw probe profile fields name the
recipe; candidate.json is the explicit unadopted identity envelope. New source
and WASM reports bind the same files, and restored source/object output matches
completely. Old actual artifact tests are not claimed to have run on this candidate.

No additional unresolved evidence consistency finding found in self-review.
Independent review of the final PR is pending; no final approval, new profile,
licensing acceptance, merge or publication is performed by this self-review.
