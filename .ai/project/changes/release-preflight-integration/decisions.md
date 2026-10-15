# Decisions

- #1309 approved design, #1322–#1327 merged prerequisites.
- One coherent S all-target collection boundary (complexity 6, High assurance),
  split internally into Actions transport and orchestration modules, no producers changed.
- Main-only manual validation entry now; central release.yml reuse/cutover remains
  #1311, without prematurely enabling public paths.
- Validate successful main CI rather than repeat its full compatibility suite.
- API all-pages/attempt/job/step/name/time/digest checks supplement producer JSON;
  explicitly do not claim uploader-job cryptographic attribution absent in API.
- Retain original payloads by immutable artifact reference and complete proof reports,
  plus exact final OCI index/blobs in one final non-authorizing artifact.
- Actual dispatch cannot run this new workflow before its default-branch merge.
  PR uses Refs #1321, never Closes; issue stays open for 13-target runtime evidence.
- Failed-only re-runs cannot reuse old candidate/attempt proof. Use all-jobs retry.
- Independent implementation/integration reviews and human merge approval pending.
