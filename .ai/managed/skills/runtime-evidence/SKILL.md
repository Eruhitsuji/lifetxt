---
name: runtime-evidence
description: Run the local-first AI history export, analyze, and report pipeline safely, with privacy and human-approval gates built into the steps instead of left to be rediscovered from script source.
---

# Runtime Evidence Skill

Packages the `standards/core/RUNTIME_EVIDENCE.md` pipeline
(`scripts/export-ai-history.py` -> `scripts/analyze-ai-history.py` ->
`scripts/report-ai-findings.py`) as one procedure, so its privacy defaults and
approval gate are followed every time rather than re-derived from each
script's source.

## When to use this skill

The user asks to collect, analyze, or report on local AI development history,
or a runtime finding needs to be produced.

## Procedure

1. **Check `.ai/project/AI_HISTORY.yml` first.** If `runtime_evidence.enabled`
   is `false`, stop and tell the user collection is disabled for this project
   — do not collect anyway. Confirm `collection.default_mode` before choosing
   flags in the next step.
2. **Export.** Run `scripts/export-ai-history.py` against the target project
   directory.
   - Default to metadata-only collection (no `--include-raw`). This is the
     documented, privacy-preferred mode; per `RUNTIME_EVIDENCE.md`'s "Checks
     by Collection Mode", it supports project-association and
     provider-coverage findings but not write-scope, repeated-failure, or
     protected-operation findings.
   - Only pass `--include-raw` when the user has explicitly approved raw
     collection for this run, understanding it embeds literal session content
     in the local archive. Never enable it silently to "get more findings."
   - Use `--dry-run` first when the matched file count or project association
     is uncertain.
3. **Analyze.** Run `scripts/analyze-ai-history.py` against the produced
   archive. Report the number of normalized events and findings exactly as
   printed — do not round up, estimate, or claim a check ran if the archive
   mode structurally could not produce it.
4. **Report.** Run `scripts/report-ai-findings.py` to render sanitized
   findings. Confirm the rendered output still excludes raw transcripts, code
   snippets, secrets, local home paths, and private URLs per
   `RUNTIME_EVIDENCE.md`'s "Privacy and Redaction Defaults" — spot-check the
   output yourself rather than trusting the redaction pass blindly.
5. **Classify each finding** as a Project/Execution finding (belongs in the
   downstream project) or a Standard/Upstream finding (may become an issue in
   this repository), per `RUNTIME_EVIDENCE.md`'s "Finding Classes".
6. **Do not open a GitHub Issue automatically.** Issue creation from findings
   requires a reviewed wrapper or explicit human-approved workflow, per
   `RUNTIME_EVIDENCE.md`'s "Initial Tooling" section. Present the sanitized
   findings to the user and let them decide whether, and where, to file them.
7. Before sharing any finding outside the local environment, get explicit
   human approval if it would include project-identifying or
   source-identifying evidence, per "Privacy and Redaction Defaults".
