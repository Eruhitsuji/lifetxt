# Decisions and remaining adoption question

Build success, source/object verification and actual Node/Chromium success do
not make the new bytes the old candidate. Keep all live pins and historical
proofs unchanged. Existing fixed-profile rejection is a successful safety check.
Either restore old exact bytes elsewhere, or review a new explicit distribution
profile for the rebuilt candidate. This PR proposes neither automatic adoption
nor a silent hash update.

Observed Python build time changed from 10:03:24 to 16:15:59 in sys.version.
Generated sysconfig includes build-location data; the outer loader BUILD_ID rule
uses generated ASM/WASM files. These are relevant reproducibility observations,
not a complete attribution of every changed binary byte. Old raw binaries were
unavailable, so only the retained hash/size records could be compared.

The browser run uses an isolated PoC layout (17 fixtures), not the completed
bilingual website checker/16KiB acceptance or its final manifest. Those remain
#1417. Source-specific ICU applicability, retained-source responsibility,
independent final distribution acceptance and Owner publication remain
#1398/#1400. Neither this source recipe name nor review of these records clears
publication flags.

The new staging_input_check survives the retained report and complete restore
recheck; live profile/final artifact consumption is still pending adoption.
Public logs normalize workspace/host-local/temporary paths. Full raw evidence
is inside the private checkpoint. Private retention does not grant public
third-party binary/source distribution permission.
