# Stage 3 Web run contract — Decision W1 (owner approved 2026-10-16)

W1 was explicitly approved by the owner on 2026-10-16 and is implemented in
PR #1349. #1347 merged into 18d5c905. The approved three-PR plan remains:
complete #1342 and #1343 in feature/1343-procedure-web → main. No fourth
implementation PR is needed. Final latest-head review/CI/merge remain separate.

## Recommended identity and authorization

Use the existing legacy Web `api.token` authentication, with a server-assigned
`web-shared` actor. Never accept actor, source path or log path from a request.
Require a configured nonempty token and an exact validated Bearer header for
all run reads/writes. Missing token configuration disables run controls while
keeping definition browsing available under existing read policy. Use constant-time comparison in the procedure adapter in addition to existing
authentication middleware; do not infer identity from
browser storage, query strings, an actor form, Remote cookies or headers intended
for proxy principals.

The existing single API credential denotes one shared operator. People sharing
that token share a run owner; this does NOT provide separate human identities or
multi-user ownership. Different CLI actors cannot be taken over, even by a Web
request supplying their actor name. Local OS users able to edit log files remain
inside the trusted filesystem boundary; this is not a cryptographically signed
audit log. Token rotation retains the shared actor and its existing runs.

Remote-enabled servers refuse these legacy run endpoints. Do not add Remote or
MCP capabilities, scopes, principal registry integration or automatic external
actions. Full multi-user access is a separate contract, not an implicit fallback.
An alternative is to finish with definition browsing only; another is a larger
Remote principal/scopes design requiring a separately approved expansion.

## Server-selected source and log

Browse all configured read sources; run writes operate only on definitions in the
existing canonical writable target. Enforce existing generated/read-only target
checks on that source and the log. Other sources have a visible browsing-only
reason. Only nodes in the selected validated same-file/root projection can be
used; no client-selected path, cross-root or hidden step can be traversed.

Select one event-only sidecar: `<writable_path>.procedure-runs.txt`. Preserve
missing-log sentinel and existing logs. The sidecar is separate from ordinary
Tasks and must never be added to normal Items automatically. CLI interoperability
uses that exact explicit `--log` path; CLI has no implicit actor adoption.
Reject aliases/hardlinks/symlinks/generated/unwritable logs through the existing
store. No new configuration setting, event schema, retention deletion or data
migration. Existing journal/backup and explicit operator recovery remain intact.

## Implemented API and browser behavior

- A procedure-owned snapshot/receipt GET API filters to `web-shared` runs and
  rejects a foreign run ID before returning its state or receipt. Includes exact
  source/root/template/log revisions, current step, sequence, allowed actions and
  a read-only/blocked reason. No event bodies, paths or other actors are disclosed.
- A closed POST body carries operation, opaque configured source token, root/run
  ID, request ID, exact bound template/log revisions, expected step/sequence, and
  optionally an explicit choice or start-loop acknowledgement. Reject unknown or
  missing fields and wrong types. Auth/read-only checks precede log access.
- Validate same-origin Origin and Fetch Metadata; JSON only. Keep the outer
  server revision check as defense in depth, but use the procedure store's exact
  log CAS as the authority. Do not commit a template through generic mutation.
- The shell may be served like the existing public `/` shell so a password input
  can supply the token in memory to Bearer requests. Never persist the token in
  local/session storage, URLs, logs or procedure events. Hide run controls until
  authenticated; clear credentials on explicit sign out and page close.
- Keep definition and execution modes visibly distinct. Never start from browsing
  or advance after page load/reload, polling, selection, a timer or an external
  event. Users explicitly start/next/choose/pause/resume/finish/abandon. Confirm
  loops and abandonment. Two clicks disable the whole control group immediately.
- Persist only the opaque run ID in the URL for reload; fetch server state again.
  Freeze the exact displayed preconditions with each action. A 409/403 invalidates
  controls and offers explicit reload; do not automatically retry mutations.
- On uncertain transport outcome retain the original request ID, query its
  read-only receipt and show whether that request committed. A missing receipt
  does not authorize replay. Pause/abandon on a changed template remain available
  against the original frozen binding; other transitions remain blocked.

## Required verification and approval

High assurance: real HTTP token/read-only/foreign actor/source/choice checks;
2 independent runs; concurrent tabs with one CAS winner; duplicate request;
changed/missing source; uncertain-response receipt and reload recovery; inherited
journal failures; keyboard, screen-reader text alternatives, 390px/mobile and
 desktop browser E2E; full relevant regressions. Review implementation, security
and integration at the latest commit. No production server changes, migration,
release, deployment or merge is authorized by W1.

Rule basis: change.yml `human_approvals_required` explicitly requires
"Server-authenticated Web actor/ownership contract before stage 3 writes";
requirements.yml now records W1 as approved. D1–D4 approved the local
procedure model and three delivery stages, but do not select this server identity
or sidecar policy. W1 approval selects the concrete proposal above; final latest
head review, CI and merge remain separate human gates.


W1 was explicitly approved by the owner in this session on 2026-10-16.
Implementation is retained in PR #1349; merge/release authority is unchanged.
