# Decisions

Owner accepted Linux-only helper conditions in #1112 and feature-specific Linux official / others unofficial with unavailable chunk denial in #1115 (comments 6013865274 and 6013887214). Existing other OS core parser/CLI/attachment operations remain as before. No mandatory dependency, configuration setting or public schema added. Native helper source pinned to reviewed digest, fixed module-adjacent artifact, no inherited preload environment.

Task decomposition #1116 primitive, #1117 explicit distribution, #1118 supervisor, #1115 adapter; each has a dedicated branch/PR. Human implementation/security and integration reviews/merge remain pending. Revert code only with explicit security review: old reader risks return. To disable safely, stop server/remove helper+manifest/restart; chunks unavailable, no source data migration.
