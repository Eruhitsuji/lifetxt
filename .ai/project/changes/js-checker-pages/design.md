# Opt-in JS checker Pages artifact

The existing manual Pages workflow selects the JS site only when the
include_js_checker input is enabled. Pull requests build and audit both
variants with read-only permissions. The upload and deploy guards still
require official main, manual dispatch and the existing protected environment.

The offline audit checks the exact output file set, same-origin local asset
and page links, checker JS/CSS/license bytes, CSP before the one permitted
module, and no active elements on introduction pages. Checker pages remain
noindex. Their presence is explicit in the audit mode. No legacy runtime or
derived source is copied. Test both variants, altered outputs, and the
bilingual local browser behavior before merging.

Rollback uses a manual main run with the checker option unchecked. The
Owner reviews and approves the introduction-only artifact and checks live
navigation, checker URLs and removed assets after deployment.
