# Daily Flow post-merge technical assessment and owner decision

Issue [#1159](https://github.com/Eruhitsuji/lifetxt/issues/1159); assessment dated 2026-10-09 JST.
Target integrated main: `f3c141d6d4ab1778344679b5982b3432010aa83e`. Executor: Codex. Standard maintenance.

## What this assessment establishes

This is a new, non-backdated AI technical assessment of the integrated source,
existing contracts/tests and attributable GitHub records. It is not a submitted
human review, independent final approval, High risk acceptance, release approval,
physical iPhone test or VoiceOver observation. It does not relabel the seven
historical PRs as reviewed before merge. Current metadata retains their gaps.

The seven PRs were already merged. Historical head/merge/CI values remain in
[the #1158 report](post-merge-evidence.md). No new historical review object was
found in the freshly queried Reviews API for these seven PRs. GitHub attribution
to Eruhitsuji identifies the posting account, not necessarily a separate human
reviewer; executor-authored implementation summaries do not establish independence.

## Assessed scope and evidence

| PR | Review viewpoints | Inspected source | Technical result |
| --- | --- | --- | --- |
| [#1148](https://github.com/Eruhitsuji/lifetxt/pull/1148) | Requirements/design | docs/en/daily-flow-lite-contract.md; docs/ja/daily-flow-lite-contract.md | D1 uncertainty blocks placements; D2 full positive est, no elapsed subtraction/splitting, explicit rest; D3 existing rank and explicit workspace day/window. Design approval is separately sourced, not final implementation approval. |
| [#1150](https://github.com/Eruhitsuji/lifetxt/pull/1150) | Core implementation/integration | lifetxt/daily_flow.py; lifetxt/daily_flow_model.py; lifetxt/daily_flow_time.py | Bounded input/edges/text/event expansion/conflicts; no file/network IO; candidate selectors preserve full occupancy/dependency context; conservative invalid/recurring/DST handling; deterministic sort, source tokens and copy normalization. Proposals do not unlock dependencies. |
| [#1151](https://github.com/Eruhitsuji/lifetxt/pull/1151) | CLI implementation/integration | lifetxt/daily_flow_cli.py; lifetxt/entrypoint.py; lifetxt/cli.py; lifetxt/cli_taxonomy.py | Window validation before reads; explicit active sources/archives excluded by default; aliases deduplicated, stdin bounded/read once; aggregate bound; actual byte revisions and one race retry; terminal control escaping; no source writes or new engine. |
| [#1152](https://github.com/Eruhitsuji/lifetxt/pull/1152) | API implementation/security/integration | lifetxt/daily_flow_web.py; lifetxt/webapp.py; lifetxt/surface_runtime.py; lifetxt/surface_runtime_compat.py | GET-only, required bounded parameters, existing local Bearer admission; exact-route runtime bypass preserves auth and avoids legacy revision reads/writes; generic error/blocked inventory; registered active files only, candidate selection not authorization; no-store and no raw source paths in model. |
| [#1153](https://github.com/Eruhitsuji/lifetxt/pull/1153) | Planner implementation/integration | lifetxt/web_planner.js; lifetxt/web_planner.html; lifetxt/web_planner.css | Explicit GET request, canonical row order and no browser scheduling; textContent output; stale generation/abort guards for date/scope/view/window/detail races; EN/JA reason codes and unsaved/incomplete labels. Current files include PR1155 additions, so this is current integrated review rather than an unchanged historical-head claim. |
| [#1155](https://github.com/Eruhitsuji/lifetxt/pull/1155) | Today presentation/integration | lifetxt/web_planner.js; lifetxt/web_planner.html; lifetxt/web_planner.css; lifetxt/webapp.py | Workspace current_datetime with monotonic age validation; unknown/stale/date mismatch falls back to Standard; custom HH:MM ordered bands, local preferences; hidden sections/section order remain authoritative; manual mode is session-only; actual completion remains sourced from native evidence, not suggestions. |
| [#1157](https://github.com/Eruhitsuji/lifetxt/pull/1157) | Scope/upcoming implementation/integration | lifetxt/read_scope.py; lifetxt/temporal_review.py; lifetxt/webapp.py | Selection of authoritative targets before association of native history; reject duplicate selected IDs/ambiguous parents without record disclosure; malformed attributable events retain native validation; current/upcoming targets stay scoped, native history excluded from upcoming; reuse Agenda max sentinel and finite recurrence cap. |

No new blocking product defect was identified in this bounded assessment.
That is not proof that all defects are absent. Source/code-review and focused
test results apply to the target integrated main, not every historical runtime
snapshot or future commit. Core/CLI files are unchanged from their historical
heads; API webapp.py, Planner files and PR1155 webapp.py contain later changes.
PR1157 source files are unchanged from its final head. Source comparisons use
the merged PR base (merge first parent), not just the last metadata-only commit.

## Located approval and implementation records

- [PR1148 comment](https://github.com/Eruhitsuji/lifetxt/pull/1148#issuecomment-6057384675):
  D1-D3 requirements/design approval and merge authorization for its exact head;
  no inference of subsequent independent implementation/integration review.
- [Issue1146 approval report](https://github.com/Eruhitsuji/lifetxt/issues/1146#issuecomment-6059751455):
  scoped API design/admission approval; it explicitly retains final-head human review.
- [Issue1146 delivery](https://github.com/Eruhitsuji/lifetxt/issues/1146#issuecomment-6060079978):
  executor test/delivery report at head 36804e958d492221aeb9e142a8cdd4f515d01928,
  not independent approval.
- [Issue1147 contract](https://github.com/Eruhitsuji/lifetxt/issues/1147#issuecomment-6060483340)
  and [delivery](https://github.com/Eruhitsuji/lifetxt/issues/1147#issuecomment-6060925720):
  UI scope/verification with human review pending; physical iOS/Safari/VoiceOver
  explicitly not claimed.
- [Issue1149 approval report](https://github.com/Eruhitsuji/lifetxt/issues/1149#issuecomment-6069732159)
  and [delivery](https://github.com/Eruhitsuji/lifetxt/issues/1149#issuecomment-6070038075):
  custom bands/current_datetime approved; iPhone and human screen-reader unrun.
- Issues1143/1144/1145/1154/1156 returned no comments at this observation.
  Empty comments or merge are not evidence of missing or completed external review.

## New verification

Python 3.12.14 / Linux / Bash. Source tree stayed unchanged during the run.
Metadata-only task; no new runtime tests or mandatory dependencies added.

```bash
python -m unittest tests.test_daily_flow tests.test_daily_flow_performance tests.test_daily_flow_cli tests.test_web_daily_flow tests.test_web_planner tests.test_web_planner_browser tests.test_read_scope tests.test_temporal_review_scope tests.test_temporal_review tests.test_change_package_closeout tests.test_traceability_gate
```

Result: 167 tests run, OK, 1 skipped (Chrome/Chromium unavailable), 13.368s.
The skipped case is the phone/language/state matrix, not the API tests.
The browser-path-selection unit case passed; this does not exercise a browser.

- Existing 17 closeout/traceability tests passed separately (1.111s).
- `node --check lifetxt/web_planner.js` and
  `node --check tests/browser_planner_probe.mjs`: passed.
- `python -m ruff check lifetxt tests scripts`: passed.
- Direct ASGI smoke: four requests passed (unauthenticated rejected before reads,
  authenticated canonical fixed/candidate result, invalid-window generic 400,
  corrupt-input blocked result). Source bytes/directory inventory unchanged.
  Reproduce with the retained [probe](post-merge-asgi-probe.py):
  `PYTHONPATH=. python .ai/project/changes/daily-flow-lite-core/post-merge-asgi-probe.py`.

This limited probe is additional evidence; it does not replace the 16 existing
API contract tests, independent approval or device verification. Full-suite,
browser matrix, iPhone/Safari/VoiceOver and release checks were not rerun here.
Prior final-head CI and browser results remain historical as in the #1158 report.

## Remaining risks and proposed owner disposition

Recommended disposition is limited to the existing experimental capability,
with no permission to weaken auth, occupancy safety, branch protection or the
ordinary independent-review rules for this PR/future changes. A human must review
this assessment and any relevant source/diff before asserting a human review.

1. Review all seven rows and record a dated post-merge human review of target
   `f3c141d6d4ab1778344679b5982b3432010aa83e`, or explicitly accept the historical review-evidence gaps
   as a maintainer disposition. Do not invent historical approval or backdate it.
2. Separately accept the retained High core/CLI/API risks: shared internal caller
   occupancy certification; conservative DST/recurrence blocking; stale snapshots
   after response; local full-workspace Bearer boundary (not Remote principal auth);
   ordinary-file filesystem trust/hostile replacement outside the Lite guarantee;
   soft deadlines and full estimates without elapsed subtraction. No new behavior.
3. For real iPhone/Safari/human screen-reader testing, either supply actual
   dated findings or explicitly accept **not_run** for this experimental state.
   Accepting this disposition closes an evidence gap, not a device test; it must
   never be represented as passed. Keyboard/layout automation is not VoiceOver.

The concrete proposed dispositions are [machine-readable here](post-merge-owner-decision.yml).
They all remain awaiting_owner. A generic implementation request or merge alone
does not accept these distinct risks or resolve #1159. Until a dated owner response
covers them, #1159 stays open and no Closes keyword is added to the evidence PR.

Authority: `.ai/project/ROLES.yml` marks major_risk_acceptance human-only;
`.ai/project/ASSURANCE.yml` High requires implementation/integration review and
human approval; `.ai/managed/core/INDEX.md` forbids sole final AI approval of its
own work. #1159 explicitly allows evidence or authorized owner disposition.

## How to record the outcome

Record the owner, date, response URL, actual reviewed commit and the scope of
each accepted/disallowed disposition in the decision YAML. Preserve unrun tests
and historical ledgers. Then synchronize package evidence gaps and traceability
and rerun the existing metadata checks. If actual device tests or source repairs
are required, keep the corresponding gap open and track the concrete work.

Metadata verification: six changed/new YAML files parsed; local report/probe/decision links valid; original verification and post_merge_reconciliation mappings retained unchanged; all three owner decisions still awaiting_owner; experimental status unchanged. Existing 17 closeout/traceability tests and scoped probe format/lint passed.

## Partial user confirmation — 2026-10-09 08:58 JST

The owner reports A1/A2 checked and requests recording the current result.
Source: [issue1159 dated record](https://github.com/Eruhitsuji/lifetxt/issues/1159#issuecomment-6071421086).

| Item | Checklist scope | Recorded result |
| --- | --- | --- |
| A1 | Planner Today rendering and scrolling | user_confirmed |
| A2 | Morning/Daytime/Evening/Standard switching and continued access to unfinished tasks | user_confirmed |

This supersedes the aggregate device status only to partial_user_confirmation.
The original not_run snapshot remains historical. Detailed observations, defect
status, device/OS/browser/language and tested commit were not supplied; do not
infer them or label every individual expectation passed. A3–A9 and V1–V3 remain
unconfirmed; no human screen-reader test or overall device pass is recorded.
This report does not authorize the three pending owner dispositions. #1159 remains open.
