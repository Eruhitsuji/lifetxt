# HKSCS-2004 permission enquiry — prepared, NOT SENT

Historical unsent draft: Owner chose verified HKSCS removal (#1416/#1417). This enquiry is superseded and must not be sent as a next step. Retained solely for audit history.


Recipient: Common Chinese Language Interface Support Team, Digital Policy Office
Email: clis@digitalpolicy.gov.hk
Verified source: https://www.digitalpolicy.gov.hk/en/our_work/data_governance/policies_standards/ccli/contact/
Subject: Clarification / permission for redistribution of CPython HKSCS-2004 derived tables in an open-source WebAssembly checker

The following is the complete proposed message. It does not assert an existing
grant, a prior contact or authority to agree to new contractual terms. Sending
requires the maintainer's explicit instruction; private correspondence is not
automatically public evidence and its publication would require separate care.

---

Dear Common Chinese Language Interface Support Team,

I maintain lifetxt, an open-source plain-text task and calendar format/tool:
https://github.com/Eruhitsuji/lifetxt

We are preparing, but have not publicly deployed, a browser-based grammar and
item checker. It processes user-supplied UTF-8 text locally and does not need a
Big5/HKSCS feature. Its proposed runtime is the unmodified Pyodide 314.0.7 release,
which includes CPython 3.14.2 and the built-in `_codecs_hk` extension with generated
HKSCS-2004 mapping tables. The entire WASM binary, not only the modules exercised
by our checker, would be downloadable from our website.

Relevant upstream source:
https://github.com/python/cpython/blob/v3.14.2/Tools/unicode/genmap_tchinese.py
https://github.com/python/cpython/blob/v3.14.2/Modules/cjkcodecs/_codecs_hk.c
https://github.com/python/cpython/blob/v3.14.2/Modules/cjkcodecs/mappings_hk.h

The generator identifies this HKSCS-2004 source/terms page:
https://www.ccli.gov.hk/en/archive/terms_hkscs-2004-big5-iso.html

We read clauses5 and15 as requiring clarification for our use: the distributed
CPython C tables are generated representations, and the runtime contains them
in compiled WebAssembly form, rather than distributing only the complete,
unmodified original mapping document. We do not wish to assume that the Python
or Unicode licences override any applicable rights in the HKSCS input.

Could you please confirm in writing whether the existing terms authorize:

1. generating/reformatting these HKSCS-2004 mappings into source tables and
   compiling them into software;
2. worldwide redistribution of those derived source tables and compiled
   binaries, together with the relevant source and copyright/permission notices;
3. open-source redistribution and downstream reuse/modification, including
   possible commercial redistribution by downstream users?

If the current terms do not authorize that scope, could the relevant rights
holder(s) grant written permission for it, or identify an officially licensed
alternative dataset appropriate for this use? Please specify the exact dataset
and scope, any required notices/attribution or other conditions, and whether
additional third-party licensors must provide permission. We would appreciate
a citable public clarification or permission to publish your relevant reply as
evidence in our repository, but will not assume permission to publish private
correspondence.

The project itself is MIT-licensed; the runtime includes components under their
own licences, including CPython/PSF and Pyodide/hiwire/MPL-2.0. We do not propose
to relicense HKSARG material as MIT or to remove its notices. The checker is
currently planned as freely accessible; the question above deliberately also
covers downstream commercial use so we do not rely on an unstated noncommercial
restriction.

Until this question is resolved or the relevant runtime data is verifiably
removed/replaced, our distribution gate remains blocked. We have not treated
our own approval or the use of similar codecs elsewhere as permission from you.

Thank you for your guidance. If another office handles this question, please
let us know the appropriate contact.

Kind regards,
Maintainer of lifetxt
https://github.com/Eruhitsuji/lifetxt

---

No message has been sent by Codex. No additional licence, reply, fee commitment
or contractual acceptance has been obtained. This draft may be revised by the
maintainer before sending.
