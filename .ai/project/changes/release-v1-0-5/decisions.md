# Decisions and authority

- Maintainer selected version 1.0.5.0. Existing canonical contract maps N=0 to v1.0.5; no numbering behavior change.
- Reuse cap-stable-release-governance. No new capability or release mechanism.
- Operations / Regulated, M with justification: Core/Mini version consistency and notes belong in one reviewable PR, actual publication remains a separate gated phase of issue #1668. Complexity 6/10 for preparation.
- Human merge and run-specific release approval are separate. The request for a release version does not constitute the latter.
- The source is main 4a36fb0ec3132949123b8d1b9635a002f7dcb9a5, 470 commits ahead of v1.0.4.3 before this change.
- Review latest main CI, unresolved critical defects and real environment acceptance before publication; unavailable evidence is not a pass.
