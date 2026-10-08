# Daily Flow Lite: proposed scheduling contract

Investigation #1143 for Epic #1142. **Proposal, awaiting @Eruhitsuji's
requirements/design approval. No scheduler, command, endpoint or UI ships here.**
The Japanese companion is [here](../ja/daily-flow-lite-contract.md).

## Task and approval boundary

Phase: Requirements & Design; Investigation; S; complexity 4/10 (scope 1,
dependencies 1, uncertainty 1, verification 1, operations 0); Standard assurance.
Inherited adaptive-default/Kanban/W-model. Executor: Codex. Independent
requirements/design reviewer and decision/merge authority: @Eruhitsuji (review
pending). Write scope: these EN/JA design notes and child-Issue refinement only.
No runtime, Format 1.0, generated schema, configuration or managed-standard edits.

Traceability: proposed `req-daily-flow-planner-lite` -> proposed
`cap-daily-flow-planner-lite` -> #1142 -> #1143 -> design PR/evidence. These IDs
are proposals, not entries claiming a shipped capability; register during #1144.
Child Issues remain inbox until approval, dependency completion and readiness.
Rollback: revert this additive documentation; no user data changes.

## Verified facts and capability reuse

Inspected main commit `8b16fcfb` (2026-10-08). These are facts; all policies below
are proposals. Source links are repository-relative.

| Registry ID | Existing seam / verified limitation | Evidence |
| --- | --- | --- |
| `cap-next-actionable-convergence` | [nextaction.py](../../lifetxt/nextaction.py): open/in-progress, no parked tags or unresolved dependencies; kinds T/D/R/H. `blocked_map` includes dangling references; compute on whole authorized workspace before task filters. | [test_nextaction.py](../../tests/test_nextaction.py) |
| `cap-next-priority-ranking` / `cap-next-why-explanation` | [extra_core.py](../../lifetxt/extra_core.py) `command_next` and [extra_common.py](../../lifetxt/extra_common.py) `_rank_key`: overdue-date bucket, priority, due-date, created-date, line. Reject invalid due in ranked mode. | [extra_core.py](../../lifetxt/extra_core.py) `_next_action_explanation` and CLI next tests in [test_extra_cli.py](../../tests/test_extra_cli.py) |
| `cap-freebusy-detection` | [freebusy.py](../../lifetxt/freebusy.py) calls [agenda.py](../../lifetxt/agenda.py) `item_time_matches`; only E/R attendance fields occupy time. Due/do/notify are not occupancy. Recurrence skipped; at-only and unmatched from/to are instants. Busy union merges touching spans; conflicts require actual overlap. No status filter in `compute_freebusy`. | [test_freebusy.py](../../tests/test_freebusy.py), [test_freebusy_cli.py](../../tests/test_freebusy_cli.py) |
| `cap-importance-priority-matrix` | [priority_matrix.py](../../lifetxt/priority_matrix.py) `classify_item`: due-derived urgency and authored importance are separate from priority. Date-only due lasts through the day's inclusive final microsecond. `matrix_rows` itself does not resolve dependencies. | [test_priority_matrix.py](../../tests/test_priority_matrix.py) |
| `cap-daily-command-center` | [command_center.py](../../lifetxt/command_center.py) `_next_actions` calls `next_action_items`, whose `_sort_key` uses mapped priority and raw due-or-do plus line, **not CLI rank**. Reuse eligibility; do not claim both sorts agree. | [nextaction.py](../../lifetxt/nextaction.py) |
| `cap-workspace-aware-timezone-context` | [timezone_policy.py](../../lifetxt/timezone_policy.py): resolve context, interpret dates/times, detect folds/gaps. Legacy `freebusy._naive` explicitly converts aware values to host local time; it is not a workspace-zone certification layer. | [test_timezone_policy_v2.py](../../tests/test_timezone_policy_v2.py) |
| `cap-web-mobile-planner` | Planner remains a consumer of shared models; Day/Week/Month and Past Review stay independent. | [web_planner.js](../../lifetxt/web_planner.js) |

Scope selectors: [read_scope.py](../../lifetxt/read_scope.py) (area and saved_view
are mutually exclusive), [agenda.py](../../lifetxt/agenda.py) `filter_items` for
project. Effort: [Format 1.0](life_txt_format_spec.md),
[timeutil.py](../../lifetxt/timeutil.py) `parse_elapsed`,
[validator.py](../../lifetxt/validator.py) W222/W226. `est` means estimated effort;
`elapsed` means accumulated actual time. Neither defines a remaining-time budget.
Source revisions must reuse the repository's existing snapshot/revision helpers
selected during #1144; do not invent a Git-only revision (plain files work too).

## Human decisions needed

Approval of this memo's policies is required before #1144 is Ready. Owner:
@Eruhitsuji. Approval should name D1-D3; editing a draft is not acceptance.

| Decision | Recommended policy | Alternative / tradeoff |
| --- | --- | --- |
| D1: uncertain occupancy | Suppress all candidate placements for the selected window if any potentially relevant E/R occupancy cannot be certified. Show fixed known spans, markers, inventory and diagnostics. | Place into apparently free spans with warnings: more useful output, but risks recommending overlapping work; deferred. |
| D2: duration and rest | Require a single positive valid est; reserve the full estimate, never subtract elapsed. No splitting. Break/buffer default to explicit zero policy; caller can request nonnegative minutes. | Require remaining estimate or personal rest defaults: needs new semantics/configuration and separate approval. |
| D3: ordering/time/sources | Reuse CLI ranked key, add stable source tie-break; importance is context only. Explicit date/window, workspace zone, active source set; reject past dates and DST-transition-day placements for Lite. | Importance-first/deadline-first ranking, retrospective simulation, DST-day placement or implicit hours need additional policy and tests. |

CLI naming/flags and Web URI/auth/visibility are **not approved by D1-D3**.
#1145 and #1146 retain their own public-interface approval gates. #1146 stays High
assurance for a public API; it cannot downgrade merely because the route is small.

## Proposed input and temporal contract

Immutable input snapshot: all explicitly selected active, authorized workspace
items; source revisions; configuration/scope snapshot; selected date; window;
resolved workspace timezone; injected `evaluated_at`; policy version and limits.
No inferred hours, weekdays, holidays or working-day calendar. Weekend requests
are allowed only with the same explicit window. Missing window -> input error;
no new working-hours config is introduced. Any future config setting needs the
project's full configuration-setting completion contract.

Window is half-open [start,end), within one selected local calendar day; end may
be the following midnight solely as that day's exclusive boundary. Resolve
local values via `timezone_policy`, preserve authored offsets and compare actual
instants. Explicit CLI timezone uses existing precedence; Web uses workspace zone.
Date-only do permits the full selected day; datetime do is an earliest-start
constraint, not a fixed appointment. Future do -> unplaced `future_intent`;
past do permits consideration. Multiple or invalid do/due -> unplaced diagnostic.
Date-only due uses the matrix's inclusive end-of-day deadline; datetime due is
an actual deadline. Due is a soft target: prefer a fitting slot ending by due;
otherwise place earliest feasible slot and explain `deadline_missed`. Overdue
items remain candidates; due is never occupancy.

Today: effective start=max(window start,evaluated_at), with exact seconds retained.
Future: full requested window; rank overdue bucket relative to selected date,
importance urgency relative to effective window start (both exposed in output).
Past date: blocked result `past_date_unsupported`, no candidates or fabricated
actuals. Empty remaining today window: no placements, `window_elapsed`.

Timezone adapter in #1144: resolve temporal fields on an immutable derived copy
using shared timezone interpreters, then feed agenda/freebusy equivalent naive
**workspace wall-time** values only on constant-offset days. Never feed aware
values into host-local `freebusy._naive` and assume workspace correctness.
Validate all relevant boundaries, offsets and mixed on/at anchoring before
conversion; failure -> D1 uncertainty. Keep original values in provenance.
Reject transition-day placements (including transitions inside an event spanning
the window) and naive folds/gaps: `unsupported_timezone_window`. Fixed markers
may still be displayed with their uncertainty. No change to old freebusy/agenda.
A future certified aware adapter can lift this limitation in a separate issue.

## Sources, task pool and occupancy certification

Two scopes are essential: occupancy/dependency context is the whole authorized
active source set; project/area/saved_view narrows **task candidates only**.
A project filter must not hide a meeting that blocks the same person's day.
Use existing selectors, with area+saved_view rejected; project is an additional
existing filter. Do not silently combine unauthorized workspace data. For Web,
authorized data insufficient to certify occupancy -> unavailable/incomplete;
never leak hidden event times/counts/titles through diagnostics or gaps. Exact
security mapping belongs to #1146, not this memo.

Only T records passing `is_actionable` are proposed as work. Done/cancelled,
parked, blocked, D/R/H/E records are excluded with reason counts; rejected T
records are available in unplaced with primary reason and secondary details.
Resolve dependencies before filtering. Never unlock a dependent because a
prerequisite is merely proposed earlier. Cross-file completed dependencies work;
missing, duplicate-ID targets and cycles fail safely. Require a unique single ID
for a schedulable T; no-ID T is unplaced `missing_identity`. Duplicate IDs in the
active context invalidate placements (`ambiguous_identity`), never deduplicate by
title. Repeated source paths are admitted once by canonical source identity;
identical content at different paths is not assumed identical intent.

Only explicitly admitted active files are read; no directory/date-based archive
scan or automatic import of prior weeks. Completed prerequisites in an archive
need explicit read-only dependency-context admission, recorded separately from
active task/occupancy sources. Context-only records cannot become candidates;
conflicting identity across either set is ambiguous. This works without a
mandatory layout and is compatible with [text-only rotation](text-editor-only-workflow.md).
A source changing during snapshot collection -> retry bounded once, then blocked
`source_changed`; suggestions are never labelled committed or current forever.

Known fixed attendance uses existing E/R semantics, conservatively including
statuses exactly as freebusy currently does; no silent cancellation reinterpretation.
All-day on occupies the selected window. On+at retains **both** existing matches,
including the all-day occupancy. A genuine R at point is a displayed marker;
it does not block. E at-only has unknown duration -> D1. Half-period from/to,
invalid/nonpositive spans, missing time, mixed ambiguous pairs, recurrence and
parse failures -> D1 unless shared semantics prove the record irrelevant to the
window. Initial Lite may conservatively mark the entire window unknown even for
apparently distant malformed/recurring items; do not infer irrelevance from a
recurrence anchor. Valid complete out-of-window spans do not block. Valid overlaps
are reported and their union blocks placement; touching spans are not conflicts.

## Duration and deterministic placement

Normalize est using existing duration normalization/validation and `parse_elapsed`;
require exactly one value yielding a positive whole number of minutes. Missing,
zero, negative, malformed or conflicting estimates -> unplaced; no guessed
30-minute estimate. Over-window estimate -> `insufficient_capacity`. Show valid
elapsed as historical context only; even elapsed>=est does not prove completion.
Invalid elapsed -> warning, no subtraction. Authors can revise est themselves;
no writes here. Ignore progress for scheduling duration.

Policy: integer `break_minutes>=0` and `buffer_minutes>=0`, each <=window length;
no inferred rest cadence. Both are reserved after **every** placed task, including
the final task. A task, its break and buffer must fit contiguously in one free
gap; no rest clipped away to make a task fit. Zero lengths create no rows.
Unused free time stays free, not a fabricated buffer. Explanation states this
simple conservative packing rule, including rest after the final task.

Reuse/extract CLI `_rank_key(item, selected_date)` into a shared pure seam in
#1144 if needed, preserving existing CLI output; do not copy or substitute
`next_action_items`'s different sort. Existing key includes line; append normalized
source identity and full ID to break exact ties across files. Importance/urgency
and do constraints are exposed but do not introduce another weighted score.
Malformed due is diagnosed before ranking, not silently placed at infinity.

```text
snapshot and validate inputs, source identities and limits
resolve full-context dependency blockers; select scoped T inventory
certify E/R occupancy; merge known busy with shared freebusy semantics
classify each T; preserve every rejection with a reason
if occupancy/time/source certification fails: no candidate placement
otherwise:
  order eligible T by (existing CLI rank key, stable source identity, full ID)
  for each T (single pass):
    release = max(effective_start, authored do datetime if any)
    footprint = est + break + buffer
    inspect chronological free gaps at/after release
    choose first gap fitting footprint with task-end <= due, if any
    otherwise choose earliest fitting gap; mark deadline_missed when applicable
    reserve footprint; emit candidate, optional policy_break and buffer
    if none fits: unplaced insufficient_capacity (never split)
serialize arrays with fixed stable ordering; never mutate inputs
```

At each loop gaps contain neither fixed attendance nor prior candidate/rest rows.
Invariant: positive candidate spans; complete reserved footprint inside the window;
no intersection with busy or other suggestions; each unique T placed at most once.
Equal timestamp timeline order: fixed, candidate, policy_break, buffer, then stable
source/ID; instants are separately ordered by time/source/ID. Unplaced inventory
uses stable source/line/ID ordering; diagnostics use code/source/line ordering.
Greedy does not prove optimality: a large early-ranked task can exclude several
small tasks. No backtracking, parallel work or automatic dependent activation.

## Proposed versioned read model (not a generated/public schema)

Required fields and types; unknown values are null, never invented. Names are
proposals for #1144 and #1146 review. No schema generator or public endpoint added.

| Field | Type / semantics |
| --- | --- |
| schema / policy_version | literal `daily-flow-lite-v1` / `lite-greedy-v1` |
| evaluated_at / timezone / date | injected offset datetime / resolved zone name / local YYYY-MM-DD |
| source_revision | object: ordered source token+revision list, plus config/scope snapshot token; no absolute paths, opaque tokens at public boundary |
| scope | object: active-source tokens, context-only tokens, candidate selector metadata; occupancy scope separately identified |
| window | requested start/end and effective start/end offset datetimes |
| policy | rank reference date, urgency reference time, break/buffer minutes, limits, duration mode `full_estimate` |
| completeness | object: state `complete`, `partial` or `blocked`; occupancy `certified` or `unknown`; inventory `complete` or `bounded`; reason-code list |
| timeline | ordered array of discriminated fixed/candidate/policy_break/buffer rows |
| instants | ordered point markers; not positive-duration timeline rows |
| unplaced | ordered item reference, primary reason code, secondary codes, structured why |
| excluded | counts by kind/status/parking reason; no hidden unauthorized counts |
| diagnostics | ordered code, severity, effect, safe item ref or null, parameters |

Every timeline row: kind, start, end, source reference (null for policy rows),
why array; candidate additionally duration_minutes, rank_key and deadline_status.
Policy rows reference their candidate. Fixed rows are input-derived, not changed
by the scheduler, and may overlap other fixed rows. Every why entry:
`{code, params}`; renderer maps code to EN/JA text, no opaque score or AI prose.
Example: `eligible_task` -> "Open task; dependencies resolved" / "未完了タスク・依存解消済み";
`full_estimate` -> "Reserved full estimate; elapsed is history" / "見積全量を確保・elapsedは実績".
Codes must survive localization unchanged. Explanations require text labels, not
color/hover alone; fixed versus suggested labels stay accessible.

Complete means context/inventory examined and occupancy certified; insufficient
capacity alone does not make data incomplete. Partial means item-level invalid
or missing inputs/candidate-limit omissions with certified occupancy; remaining
safe placements may exist. Blocked means no placements due to input/snapshot/
occupancy/identity/resource failure. Return known fixed data only if safely
available. All rows and diagnostics carry bounded provenance; no raw source text,
secrets, hidden paths or private titles in unauthorized output. Proposal token
and revisions support stale detection only, not write permission or CAS adoption.

## Diagnostics and future acceptance fixtures

Expected outcomes below are **future contract tests**, not tests of a shipped
scheduler. Existing freebusy diagnostic codes are preserved within diagnostics;
Daily Flow adds effects without changing their meaning.

| Fixture / trigger | Code and expected result |
| --- | --- |
| F1: repeat:daily E spanning the day | skipped_recurring + occupancy_unknown; blocked, no candidates |
| F2: E on:selected-date, no at | all-day fixed covers window; complete, tasks insufficient_capacity |
| F3: R at:10:00 versus E at:10:00 | R instant, no busy; E unknown_duration, blocked |
| F4: DST gap 2026-03-08 02:30 / fold 2026-11-01 01:30 America/New_York | unsupported_timezone_window; no silent fold choice or gap shift |
| F5: T without est / est:0m / est:-1m / est:90x / two est values | missing_estimate / invalid_estimate / ambiguous_estimate; unplaced, partial |
| F6: completed prerequisite in explicit context-only weekly file | dependency resolved, candidate eligible; same file omitted -> unresolved_dependency |
| F7: E 10:00-11:00 plus 10:30-11:30 | conflict warning, busy union 10:00-11:30; placements only outside union |
| F8: E from only / to only / reversed from-to | incomplete_period / invalid_span; whole window unknown, blocked |
| F9: two active records with same ID | ambiguous_identity; blocked; no title-based deduplication |
| F10: est:30m elapsed:40m, open T | reserve 30m; explain historical elapsed; never mark complete |
| F11: do tomorrow / do today at 11:00 | future_intent unplaced / earliest start 11:00; not fixed attendance |
| F12: today evaluated at 12:34:56 versus yesterday | no candidate before 12:34:56 / past_date_unsupported |
| F13: invalid E temporal field / missing E time / invalid due T | invalid_time_value or missing_time_detail blocks; invalid_due rejects only that T |
| F14: project filter excludes another project's meeting | meeting still blocks; filtered prerequisite still resolved in context |
| F15: break+buffer won't fit though task alone fits | insufficient_capacity; no clipped policy rows |
| F16: source revision changes during read / hidden occupancy under auth | source_changed blocked / generic unavailable result, no hidden timing leakage |
| F17: equal rank/line across source paths; reversed input enumeration | same source+ID tie-break and canonical JSON; no Python object identity |
| F18: resource cap exceeded | limit_exceeded; occupancy/context overflow blocked, never truncate busy silently |
| F19: window completed / touching events / on+at | window_elapsed / no conflict for touching / all-day match retained |
| F20: UTC host, Asia/Tokyo workspace, explicit +09:00 event | derived copy yields Tokyo times; old host-local conversion not used; failure blocks |

## Reproducible small scheduling example

Input date 2026-10-09, zone Asia/Tokyo, evaluated_at 2026-10-08T18:00+09:00,
window 09:00-12:00, policy break=10m/buffer=5m; all records in active `work.txt`:

```text
[ ] E Meeting id:e1 from:2026-10-09T10:00 to:2026-10-09T11:00
[ ] T A id:a priority:A due:2026-10-09 est:45m
[ ] T B id:b priority:B due:2026-10-09 est:30m
[ ] T C id:c priority:C due:2026-10-09 est:30m
[ ] T Unknown id:u
```

Expected ordered candidates: A, B, C; Unknown has missing_estimate. A fills
09:00-09:45, break 09:45-09:55, buffer 09:55-10:00; fixed meeting 10:00-11:00;
B 11:00-11:30, break 11:30-11:40, buffer 11:40-11:45. C needs 45m but only
15m remains -> insufficient_capacity, no split. Unknown unplaced -> partial;
occupancy certified. Source file byte hash unchanged. Setting break/buffer=0
allows C at 11:30-12:00. Reversing source enumeration changes nothing when source identities/line metadata
are preserved (reordering authored lines is a different input).
A deadline at 09:30 instead yields deadline_missed on A, without moving the meeting.

## Bounded performance and simpler alternatives

Proposed hard limits: 10,000 context records, 20,000 dependency edges, 1,000 eligible candidate attempts,
1,000 E/R records, 2,048 normalized occupancy intervals/free gaps, 10,000 conflict
pairs. Duration/rest bounded by requested day. Preflight record/occurrence bounds
**before** calling freebusy's conflict enumeration; conservatively bound potential
pairs by E*(E-1)/2 unless a reviewed bounded shared sweep is available; its active-list sweep can be
quadratic for dense overlap. An unsafe/overflowing occupancy context blocks all
placements, not a falsely free truncated day. Candidate cap keeps first 1,000 by
canonical rank; remaining inventory gets limit_exceeded without scheduling;
report count and bounded references, completeness inventory=bounded. Never bound
dependency context by selecting just first 1,000 tasks. If bounded references
cannot preserve required inventory, return blocked summary rather than omit.

N=context, E=bounded intervals, D=dependency edges, C=candidates, G=free gaps,
K=conflict pairs. Target O(N+D+E log E+C log C+C G+E²) worst case with existing
conflict sweep (including active-list pruning), space O(N+D+E+C+G+K). Do not claim
linear conflict detection. Slot growth from reservations is at most C; include
that in G. Hard caps bound work, not a proof of subquadratic behavior.

Target benchmark: 1,000 T + 100 E, including dense overlap, many short gaps,
unknown estimates and equal keys, one day; 20 deterministic warm runs after 3
warmups, separately measure parsing and pure-core time with monotonic clock,
p50/p95, peak memory via tracemalloc separately, Python version/OS/CPU and seed.
Proposed core p95 <=250ms and incremental peak <=32MiB on documented reference
Linux host; no speed claim measured here. Run cap-sized failure scenarios too.
If missed, profile/split follow-up before raising limits; correctness invariants
and stable output are mandatory, timing is environment-qualified.

Earliest-fit plus existing rank is bounded, inspectable and preserves familiar
choice order. Deadline-first may improve deadline completion but changes existing
priority semantics; explicitly deferred. A general solver adds dependencies,
weights, search/timeouts and difficult explanation/optimality tradeoffs for little
Lite value. No solver or machine learning dependency recommended.

## Follow-on task refinement and review

Proposed additions to existing Issue contracts; do not mark Ready automatically.

| Issue | Executable scope after approval | Required evidence / gate |
| --- | --- | --- |
| #1144 core, S | Pure model, shared unchanged CLI rank seam, immutable timezone normalization/certification, bounded greedy. No CLI/API/UI. If seam/bounds work exceeds S, split readiness subtasks first. | D1-D3 approved; all F1-F20, overlap/no-write/determinism invariants and benchmark; actual shared-contract assurance assessed (High if public schema/data contract added). |
| #1145 CLI, S | One opt-in renderer/command using canonical model; no ranking/placement code. Explicit date/window and canonical JSON. | #1144 complete; CLI interface separately approved; text/JSON parity, read-only byte checks, missing-input/error/localization tests. |
| #1146 API, S / High | One GET projection, existing admission/auth; privacy-safe provenance and limits; no scheduler. | #1144 complete, endpoint/auth/scope approval and High change package; hidden-occupancy inference tests, no absolute-path leak, model parity and error mapping. |
| #1147 UI, S | Opt-in Day panel; typed labels, reasons, unplaced/uncertainty; consumes #1146 only. | #1146 complete; 320/360/390/430px and short-height, keyboard/screen-reader, EN/JA, loading/error/stale response, Past no-actuals tests. |

Non-goals: writing/adopting do, saved intent/actual records, auto-import/archive
rotation, recurrence expansion, automatic splitting, multicore parallel work,
week/month optimization, background refresh, remote/MCP scope or permissions,
AI/external services, Format grammar/config defaults. Text-editor-only environments
still use their manual workflow; generation requires a runtime.

Risks: conservative D1 may suppress many useful days; full est may over-reserve;
legacy time seams demand regression verification; greedy is not globally optimal;
shared reads can reveal occupancy or dependencies if authorization is mishandled.
Owner accepts policies, independent review and merge; implementer self-review is
not final approval. No implementation child unblocks until the named gate passes.

## Investigation verification

Executed against inspected source: `python -m unittest tests.test_freebusy
tests.test_nextaction tests.test_priority_matrix tests.test_read_scope
tests.test_timezone_policy_v2`: **65 tests passed**. This verifies existing seams,
not future scheduling fixtures. Also executed `python -m unittest
tests.test_extra_cli`: **46 tests passed**, covering CLI ranking/explanations.
Link consistency and documentation validation
are recorded in the PR. Runtime/code quality/security changes: not applicable;
design review covers determinism, occupancy certainty, privacy and compatibility.
