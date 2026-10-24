# Decisions and limits

2026-10-25 Owner requested all review fixes, self-review and PR. #1411 is the
ready child implementation contract; #1398/#1400 publication dependencies remain
blocked. The review input targets main 372ddca1 and is retained at
https://github.com/Eruhitsuji/lifetxt/issues/1398#issuecomment-6386098797 .

P1-4: choose same-origin source bundles for all publication candidates rather
than claiming upstream generated archive permanence. A retention policy and
required Owner evidence are implemented, but no Owner retention commitment,
hosting acceptance or publication authorization is fabricated.

P2-6: local hashes bind our retrieved archives. They do not prove what upstream
compiled when its recipe lacked a hash. Actual zstd/SQLite observations and
xz official-byte equality strengthen the recorded scope; linked liblzma version
and upstream input-byte identity remain unverified. Owner judgment is pending.

P2-7: recommend official release byte identity + recipes + patch application +
stdlib mapping + runtime observations as the bounded evidence policy, with
remaining input/rebuild uncertainty recorded. A fixed-toolchain rebuild is the
alternative. Neither an acceptance nor this implementation makes unperformed
rebuilds or emsdk commit mapping verified. Independent review and Owner decision
remain pending in the template and final report.

P2-8: final review records remain outside the artifact, bound to current commit
and manifest; review authentication is a human responsibility. Actual pending
record never passes. Positive test data are explicitly synthetic.

P3-9: the Windows path failure originates in scripts/check_website.py using
str(relative_path) while expected HTML paths use slash separators. Change to
as_posix; this is an offline validator fix, not a production renderer/workflow
change. Extend the task write scope accordingly; same reviewed defect class.

Unicode current official License V3 bytes and UCD16 ReadMe were retrieved
2026-10-25, retaining their original copyright ranges and hashes. The historic
mapping-input scope is documented for independent evaluation; no blanket legal
sufficiency determination is made. No dependency upgrade or security acceptance
of the legacy runtime libraries is implied by licence remediation.
