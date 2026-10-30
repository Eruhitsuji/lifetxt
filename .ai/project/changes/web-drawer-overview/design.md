# Drawer overview design

Reuse the existing drawer, tab panels, renderer and mutation handlers. Body and named primary fields come first; other keys and source/ID/raw are native disclosures. Exact values are escaped and protected from the global translation walker. Offset-bearing dates reuse the main workspace clock timezone rather than the optional display-clock override; date-only/naive/invalid strings remain literal. Raw timestamps remain available through time title and raw record (the API text field, with legacy raw fallback). Reopening an already open drawer preserves the original opener for close/focus restoration. Overview grid styling excludes hidden panels to preserve tab visibility.

Attachments keep reference presence and availability/error/receipt outside the disclosure. Work sessions keep status outside; own running session opens controls automatically. Mount, disposal, revisions and write guards remain unchanged. Upload policy and authorization do not change. Delete remains the existing confirmed action inside a visually separated More section.

One M task (score 6) combines approved D1/D2 because both form the same Overview lifecycle and acceptance surface, per the requested larger child issue. Timeline/Relations remain separate. Native details/summary provides keyboard semantics; no new modal, service or dependency.
