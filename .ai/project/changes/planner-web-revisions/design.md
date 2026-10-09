# Design and mutation audit

The separate Planner HTML does not install the main Web fetch bridge. Use the
existing server contract through Planner's API helper rather than injecting a
second global fetch wrapper or changing the normal Web shell. Its only current
unsafe calls are the authoritative writes below; future independent-CAS routes
must be classified explicitly before being added to this helper.

| Planner operation | Route | Precondition source |
| --- | --- | --- |
| Quick Capture | POST /api/items/capture | revision of loaded Tasks snapshot, frozen when Capture opens |
| Note/Journal create | POST /api/items | retained authoritative revision frozen when editor opens |
| Note/Journal edit | PUT /api/items/id/{id} or /api/items/{line} | revision of the response supplying the edited record |
| Task complete | POST /api/items/id/{id}/complete | revision of the displayed record |
| Task without ID | PUT /api/items/{line} | revision of the displayed record |
| Habit done | PUT /api/items/id/{id} or /api/items/{line} | revision of the displayed record |

All these routes use the generic whole-file Web transaction. No Planner action
uses an intentional independent CAS exemption. Daily Flow is a GET-only projection;
configuration/agenda/views/details are reads; customization is browser local.

The helper retains successful ETag (or quoted X-Lifetxt-Revision), associates read
objects with their response token in a WeakMap, and discovers /api/revision if a
write without an explicit snapshot has no token. Explicit missing snapshots fail
closed. A failure response never advances the token and no write is replayed.
Response body revision fields on projections may have a different scope and are
not used as generic response revision tokens.

Capture's existing expected_source_revision JSON member is preserved and filled
from the authoritative loaded revision; If-Match enforces the snapshot. Inspection
of current webapp.capture_item shows it does not check that JSON member. Thus it
is not an independent enforced CAS, contrary to the preliminary task-contract
assumption. The current item-list response also lacks source_revision, so Planner
now falls back to that response's authoritative header instead of an empty string.

On 409/428, the caller retains input and shows reload instructions. Task/Habit
buttons catch errors and bound in-flight actions; editor/capture submissions
reject duplicate in-flight submits. Habit payloads copy the done list so a failed
write does not mutate the retained read object. Whole-file conflicts are deliberately
conservative; no merge/rebase is attempted in the browser.

## Review and verification viewpoints

Review data integrity, stale record vs background refresh, token provenance,
failed discovery, no automatic retry, repeat clicks, ID/line paths, and main-shell
compatibility. Node executes the complete shipped Planner JS with a minimal DOM
adapter against disposable ASGI servers in both modes. This proves handlers and
HTTP behavior, not browser layout or physical-device accessibility.

## Integration and recovery

Shared registry/docs files are integrated serially on the task branch by Codex;
Eruhitsuji is integration/merge authority. Resolve any intervening main changes
semantically. Revert this isolated client fix if necessary; there is no migration.
The main Web bridge and server middleware remain byte-for-byte unchanged.

The existing shared Quick-input handler harness supplies the frozen capture
revision when invoking the extracted Planner handler; full integration coverage
continues to execute the real open/submit lifecycle.
