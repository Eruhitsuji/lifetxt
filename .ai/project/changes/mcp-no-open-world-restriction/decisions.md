# Decisions

## 1. Independent flag, not a fourth profile value

See `requirements.yml`'s decision log. `OPEN_WORLD_TOOLS` is already an
orthogonal classification from `READ_ONLY_TOOLS`/`ASSIST_EXTRA_TOOLS`; an
independent `--no-open-world` flag preserves that orthogonality and every
existing profile's semantics unchanged, rather than requiring a fourth
profile enum value that would force a choice between "read-only" and
"no-network" instead of allowing both together.

## 2. Bundling #544 (documentation) and #545 (implementation) into one branch/PR

Both originate from the same #543 investigation and both touch the exact
same paragraphs of `docs/en+ja/ai-integration.md` section 6 -- landing them
separately would produce two PRs each editing the same lines, with the
second rebasing on the first's prose. Combined per this repository's
established "share the same concept" batching precedent (e.g. #528/#529,
#537/#538).

## 3. Correcting two pre-existing documentation inaccuracies found during this change

While rewriting section 6 to document `--no-open-world`, two sentences in
the same paragraph were found to already be false (see `design.md`'s
"Documentation corrections" section). Both are corrected in the same edit
rather than filed as separate follow-ups, since they are in the literal
lines being rewritten for this task and leaving them would mean shipping a
new true sentence next to an old false one in the same paragraph.

## 4. Not implementing resources/list/resources/read filtering

#543's own investigation (section C) recommended documentation-only for
resources, not a behavior change -- confirmed no evidence that resources
disclose anything beyond what already-permitted read tools disclose under
the same profile. That recommendation is implemented as #544
(documentation-only, tracked separately). This change does not touch
`lifetxt/mcp_resources.py`.
