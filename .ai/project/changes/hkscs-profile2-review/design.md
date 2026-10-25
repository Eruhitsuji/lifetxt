# Metadata guard and review disposition

Operations/High, W-model, S. Source main 617540fa; branch
fix/hkscs-profile2-review; final PR base main. Owner/Integrator/Merge Eruhitsuji,
Implementer Codex. Separate latest-head review pending.

The profile2 source-guide marker must occur exactly once before replacement.
Missing or repeated labels fail before artifact output. Normal generated source
instructions retain their bytes. Legacy profile does not use this guard.
Generic audit intentionally discovers a finite manifest identity and verifies its
full fixed lock. Specific caller expectations use runtime_profile explicitly;
the existing real artifact test rejects profile2 when profile1 is expected.
No default selection change, new runtime, licence resolution or flag change.

Review/test/security viewpoints: metadata truth, template drift, explicit caller
expectation, old profile compatibility, static reviewer scope and fail-closed.
Rollback: human-reviewed revert of this small guard/docs change. Undeployed.
