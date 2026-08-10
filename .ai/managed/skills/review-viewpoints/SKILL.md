---
name: review-viewpoints
description: Review a pull request against standards/core/REVIEW.md's Pull Request Review Viewpoints checklist, including horizontal-review scope discipline.
---

# Review Viewpoints Skill

Packages `standards/core/REVIEW.md`'s "Pull Request Review Viewpoints"
checklist as a direct procedure for first-pass review.

## When to use this skill

Reviewing a pull request, or asked to check a change before it is proposed for
merge.

## Procedure

Check the diff against the target issue and against each viewpoint below.
Cite concrete files and behavior for every finding — do not report a viewpoint
as satisfied or violated without pointing at what you actually looked at.

1. The change matches the linked issue and its acceptance criteria.
2. No unrelated work is included. If the issue's acceptance criteria required
   a horizontal review of adjacent code, apply
   `REVIEW.md`'s "Horizontal Review Scope Discipline": a discovered issue
   belongs in this PR only if it shares the same root cause and is small and
   evidenced; otherwise it should be a separate follow-up issue, not folded
   in and not silently dropped. A horizontal-review criterion with no
   resulting fix or follow-up issue is a sign the audit wasn't done — flag it.
3. Write scope and forbidden scope (from the task contract) are respected.
4. Behavior is correct for normal, edge, and error cases — not just the
   happy path shown in any included tests.
5. Public interfaces and data contracts remain compatible, or the
   incompatibility is documented and approved.
6. Tests cover meaningful behavior, not just implementation details or
   trivially-true assertions.
7. Security-sensitive changes received scrutiny proportionate to their risk.
8. Failure modes, logging, and observability are adequate for the change.
9. Documentation and migration notes are updated when the change requires it.
10. Commands and results claimed in the PR description were actually run —
    if you cannot verify a claim, say so explicitly rather than assuming it.
11. Review freshness: confirm you are reviewing the current head commit, not
    a stale earlier push (`reviewed_commit != current_head_commit` means the
    review must be repeated).

## Output

Report findings ranked by severity using `REVIEW.md`'s severity model (P0-P3).
State plainly which viewpoints you checked, which you could not verify, and
why. Do not approve your own implementation — an AI must not be the final
approver of a change it wrote itself.
