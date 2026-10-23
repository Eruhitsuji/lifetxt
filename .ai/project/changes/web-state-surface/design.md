# Design

Add a standalone `/state` page assembled from three packaged assets, following
Planner's resource pattern. Retain the existing authenticated route behavior
and no-store. Register only those three files in package data. There are no new
runtime dependencies, APIs, parser/mutation semantics, credentials or manifests.

Six primary tiles and a native More disclosure expose all nine canonical
states. A separate optional form supports custom state, title, note and explicit
force/restart. End closes an interval, while Offline creates one. Color uses
the existing public presence-class allowlist, with configured overrides first;
labels, icons and aria-pressed ensure meaning does not depend on color alone.
Unknown custom values remain verbatim text with a blue fallback. User-derived
values enter the DOM through textContent/value, never HTML or arbitrary classes.

Read existing config, health and self-only active/latest Status APIs. Reject
mismatched source revisions between the two Status reads and filter self again
on the client. Keep a last-confirmed display on read failure. Never substitute
another person's first record. Health controls writable state; preserve the
same existing authenticated connection as Planner without a token form.

Writes use the displayed snapshot's If-Match. Edited details pin a separate
revision which background reads and tile writes cannot silently upgrade. An
explicit Refresh reviews the latest snapshot and rebases retained input; it
never resubmits a write. Successful form submissions accept their new revision.
No-op feedback explains why same-state details remain unchanged; force is an
explicit restart checkbox. All actions disable during a write. A post-save GET
must succeed before changing the current-state display. Acknowledged writes
whose readback fails get distinct uncertain-display feedback and block writes.
Conflict, network and server errors require a fresh read; invalid input stays
editable. Inputs and last confirmed data remain intact on every failure.

Generation counters and aborts isolate stale GETs. Visible-only minute polling
and focus/pageshow/visibility handlers refresh external changes. No offline
cache, queue, retry or state automation is added. The network indicator remains
separate from the canonical offline state. All request groups have bounded
timeouts and cancellation; hidden pages do not poll.

Elapsed time anchors to the server workspace clock using performance.now,
not the browser wall clock. ISO offsets use their stated instant; naive Status
timestamps use the server's IANA timezone. Invalid times and ambiguous DST
folds/gaps show Unavailable instead of a guessed duration.

Native disclosure/form controls retain keyboard and assistive semantics. Stable
tile nodes preserve selection and focus. After pending writes, keyboard focus
returns to its original control, or Refresh if that control is now disabled;
do not steal focus if the user moved elsewhere. Flexible columns, wrapping,
16px inputs, safe-area padding and normal page flow support short/phone layouts.

Review/test viewpoints: route/auth/CAS compatibility, self filtering and temporal
state, canonical payloads, safe rendering, no optimistic success/retries, pinned
form revisions, out-of-order reads, input/focus retention, viewport/theme/AX and
wheel resources. Node DOM tests exercise interaction/transport, not layout.
Optional Chromium probes exercise native layout, keyboard/AX and real API
persistence in observe/required modes. Actual iPhone/Safari, software keyboard,
safe-area hardware and screen-reader acceptance remain device checks.

Rollback: maintainer-approved revert of the PR. No migration; written S records
remain valid. Shared-file integration and final merge belong to Eruhitsuji.

The existing real-Chromium revision CI job also runs StateBrowserTests; it
already provisions Node/Chrome/Web dependencies. Retain synthetic viewport JSON,
a synthetic screenshot and live-API summaries in its existing artifact. Do not
add jobs, triggers, permissions or dependencies, and do not claim local browser
execution when installation is unavailable.
