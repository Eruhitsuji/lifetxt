# Drawer relations

Reuse links, temporal-thread, graph and canonical item lookup APIs. Do not compute relationships or inferred dates in JavaScript. Show explicit direct links first with source-relative direction and label; preserve raw relation names, unresolved status and available type/status. Temporal lifecycle groups retain the shared reader's classifications. Nearby candidates show only the bounded API result and explicitly explain that they are derived, not saved links or an exhaustive relation list. Thread fetch failure is not an empty thread. Warnings and truncation remain available.

Fetch links/thread concurrently; bind the response to the exact item object and mounted container. The graph fetch is on demand through native details and the existing renderer; the accessible primary representation is the list. Long titles wrap, controls are at least 44px tall. All user values and unknown codes are escaped and protected from automatic UI translation.

Related record opens use the existing ID lookup. A history entry stores only its immediate origin ID/title and target ID; it is not a persisted navigation trail. A navigation token plus origin object/URL guards against old responses and closure. Failed reads retain the current record. The return control re-fetches the origin, opens its Relations tab and focuses that tab. Back/Forward restores the URL and matching per-entry context through existing deep-link restoration; direct deep links carry no inferred origin. No parent relationship is invented.

Performance: O(links + lifecycle + nearby) rendering; bounded temporal API and graph depth unchanged. No new graph layout algorithm or dependency. Rollback: revert PR; no migrations or config additions.
