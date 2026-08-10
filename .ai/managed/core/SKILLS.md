# Skills Standard

A skill is a packaged, on-demand, reusable procedure for a recurring task, as
opposed to always-loaded reference material. This standard defines a minimal
tool-neutral skill contract so AI tools with different native skill mechanisms
(or none at all) can use the same underlying skills consistently.

## Why Skills Are Different From Standards Documents

Standards documents under `standards/core/` are reference material an AI reads
and reasons about. Several of them already describe a concrete, repeatable
*procedure* in enough detail to be followed almost as written (for example,
`NEXT_ACTION.md`'s inspection sources, state classification, and output
format). A skill packages that procedure so it is invoked on demand, by name or
by trigger, instead of being re-derived from prose every time it is needed.

## Minimal Skill Contract

A skill has:

- a stable name (kebab-case)
- a one-line trigger or description, for tools that support auto-suggestion
- instructional content: the procedure itself, written so it can be followed
  directly
- optional supporting scripts or templates the procedure references

A skill must not define rules that conflict with `standards/core/**`. A skill
packages how to follow an existing rule; it does not create a new one.

## Canonical Storage

- **Standard-shipped skills** live under `standards/skills/<name>/` in this
  repository (source of truth) and mirror to `.ai/managed/skills/<name>/` in
  downstream projects, the same way `standards/core/` mirrors to
  `.ai/managed/core/` (see `STANDARD_DISTRIBUTION.md`). Downstream projects
  must not edit `.ai/managed/skills/**` directly.
- **Project-specific skills** live under `.ai/project/skills/<name>/` in a
  downstream project. This is downstream-owned, source-of-truth content,
  consistent with how `.ai/project/**` already owns project-specific rules.

## Loading

Skills are loaded on demand, not eagerly imported into every AI tool session.
Reference a skill from `.ai/project/CONTEXT_INDEX.yml` with a `load_when`
trigger, the same way other progressive-loading rules are declared. Do not add
skill files to an adapter's always-imported entry list (`CLAUDE.md`'s
`@import` list or `AGENTS.md`'s numbered "Read and follow" list) — see
`AI_TOOL_COMPATIBILITY.md`'s "Context Loading Behavior by Adapter Mechanism"
for why eager-loading more content by default is the wrong direction.

## Reconciling Third-Party Spec-Driven Tools

Some projects adopt third-party tools (for example, spec-driven-development
generators) that install their own packaged procedures into tool-specific
locations outside this standard's `.ai/managed`/`.ai/project` model. Treat
their output as generated artifacts outside the `.ai/managed`/`.ai/project`
ownership boundary, not as an alternative source of truth:

- Do not let a third-party tool's output silently redefine or contradict a
  rule in `standards/core/**` or `.ai/project/**`.
- When such a tool encodes durable, project-specific operational knowledge
  (a working invocation sequence, a known gotcha), capture that knowledge back
  into `.ai/project/skills/` or `.ai/project/RULES.md` so it stays available
  to every supported AI tool, not only the one the third-party tool targeted.

## Starter Skills

This repository ships a small starter set under `standards/skills/`, mirrored
to `.ai/managed/skills/` in downstream projects:

- `next-action`: implements `NEXT_ACTION.md`'s required inspection sources,
  state classification, and output format directly.
- `runtime-evidence`: wraps the export -> analyze -> report pipeline
  (`RUNTIME_EVIDENCE.md`) with its privacy, redaction, and human-approval
  gates built into the procedure's own steps.
- `review-viewpoints`: implements `REVIEW.md`'s Pull Request Review
  Viewpoints checklist, including horizontal-review scope discipline.

## Adding a Skill

1. Confirm the procedure is genuinely repeatable and already specified (or
   specifiable) in enough detail to follow directly — not something that still
   needs case-by-case human judgment.
2. Write the name, trigger/description, and instructional content following
   the Minimal Skill Contract above.
3. Place it under `standards/skills/<name>/` (standard-shipped) or
   `.ai/project/skills/<name>/` (project-specific).
4. For standard-shipped skills, add a `CTX-*` rule entry to
   `templates/downstream/.ai/project/CONTEXT_INDEX.yml` so it loads on demand,
   and list it in this document if it becomes part of the starter set.
