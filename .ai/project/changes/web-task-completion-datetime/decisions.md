# Decisions

- Feature / Standard, M (complexity 5), one executor/branch/PR: UI and persistence
  evidence form one acceptance boundary. User requested implementation of #861.
- Extend cap-web-drawer-record-editing and reuse existing mutation/history APIs.
- No configuration/dependency/API change. Task-only explicit completion metadata;
  do not change habit, recurrence or bulk semantics.
- Browser timezone is named in the form. UTC timestamps avoid naive timezone
  reinterpretation when client/server timezones differ.
- Review viewpoints: acceptance, backward compatibility, input safety, immutable
  undo, revision conflicts and Native History atomicity. Final independent review
  and merge belong to Eruhitsuji; no self-approval.
