# Design

The existing bulk Done remains unchanged. A separate managed modal previews
eligibility and asks for Now/date/date+time confirmation. Now captures one
second-precision UTC value at confirmation and freezes it for retries. Date-only
values remain exact; local date/time validates by wall-time roundtrip, rejecting
DST gaps and choosing the native earlier occurrence for folds (same as #861).
Native inputs, managed focus trapping/restoration, Escape handling, wrapped actions,
44px controls and live result/summary text support keyboard and narrow layouts.

Each target retains a deep original snapshot. Before each write, read health,
revision, full item list, revision; refuse inconsistent revisions. Resolve a
unique stable ID, or exact source/line for ID-less records; compare source,
ID, editable/generated and canonical full payload. Source must equal writable
path. The single-file reader deliberately returns null source; accept only if
health names exactly one input equal to the writable path. Never use the
ambiguous legacy GET-by-line route. A PUT uses the freshly read revision in
explicit If-Match, so the fetch bridge cannot replace it with a newer one.
An external edit before commit produces conflict; there is no automatic rebase.

Completion sets status and done in one existing mutation. The response item is
verified before counting success. A lost response is visible as uncertain;
retry requires the original snapshot still to match, so an actually successful
write cannot be duplicated. Undo requires the exact successful payload and
source still match, then restores the original full payload under fresh CAS.
Other tasks can change without blocking a safe restore; changes to the restored
task block it. Individual errors and retry controls remain in session even when
the modal closes. Starting with current selection explicitly replaces that
session's recovery controls. Page reload does not persist them.

Sequential writes are non-atomic. Each round resolves only pending/failed tasks
or successful/failed-Undo tasks respectively, guarded against concurrent submits.
The full-list approach costs O(targets * workspace items) time and O(workspace
items + selected payloads) space, chosen for conservative identity verification
without changing an API. Typical interactive selection sizes are expected;
no new throughput guarantee or batch endpoint is introduced.

Revert the PR to remove the action. Previously stored done values remain valid.
