# Decisions: remote-historical-evidence-read (#728)

- Dedicated route (`GET /api/remote/v1/historical`) rather than a generic
  `_BUILDERS` resource entry, per design.md's "Why a dedicated route"
  section. `resource_catalog()`/`RESOURCE_NAMES` are deliberately left
  unmodified since this is not a current-state item resource.
- `historical` scope is a brand-new, distinct scope name, never added by
  any of the four built-in roles (`owner`/`editor`/`reader`/`auditor`).
  An operator must add it explicitly per principal in
  `remote.principals[].scopes`. This was chosen over silently granting it
  to `owner`/`auditor`, since #727 Section 1 explicitly requires the gate
  to be distinct and explicit rather than inferred.
- The server-level `limit` default (200) and maximum (1000) mirror the
  existing `tickets` resource's own default/maximum precedent
  (`cap-remote-tickets-pagination`), rather than inventing new numbers.
- The conjunctive current-record check reads the current workspace via
  `webapp.read_life_inputs` inside a broad `try/except Exception: return
  {}`. This is deliberately fail-open for that one sub-check only (a
  current-read failure never blocks or widens the *historical* check,
  which already ran and is unaffected) -- not a general fail-open
  posture for the endpoint itself, which still fails closed on every
  historical-read failure via the surrounding `try/except ValueError`.
- No JSON Schema was published for `remote-historical-read-v1` in this
  slice, matching this project's own established precedent (see
  `.ai/project/CAPABILITIES.yml`'s notes on `notifications.email.smtp_port`
  lacking a schema fragment) -- the response shape is documented in
  `docs/en/remote.md`/`docs/ja/remote.md` instead. Publishing a formal
  schema is a reasonable follow-up once real client demand exists.
