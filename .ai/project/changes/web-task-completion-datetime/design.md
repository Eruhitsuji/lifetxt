# Design

Extend the existing task drawer with Done date…; keep Done and Complete + repeat.
The date form uses native date/time inputs in the scrollable drawer body, full-width
controls and 44px action targets. Cancel returns to the original record; Escape
and close use existing modal behavior. Existing done values are escaped and shown
with an overwrite notice. Now skips date input validation intentionally. Custom
uses native validity and refuses DST gaps rather than normalizing them.

Preserve date-only strings; timed input uses browser local time then explicit UTC.
Now has second precision, Custom minute input precision. In a DST fold, the native
Date constructor chooses the earlier occurrence; this is documented. No model or
API extension is necessary. The normal completion operation remains unchanged.

One existing PUT sets status and details together. Prefer configured stable ID;
retain line fallback for ID-less records. The existing fetch bridge provides
If-Match, and the existing mutation pipeline records native history atomically.
Clone the details map to preserve the undo snapshot; the in-flight guard rejects
double submission. Save failure leaves the form and original record intact.

Revert this PR to remove the UI. Already-written dates remain valid existing syntax.
