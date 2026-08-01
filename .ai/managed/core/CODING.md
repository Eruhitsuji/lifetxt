# Coding Standard

## General Rules

- Keep files and modules focused on one responsibility.
- Prefer clear names over comments that restate implementation.
- Avoid hidden global state unless the project architecture requires it.
- Keep public interfaces documented and stable.
- Do not mix formatting-only changes with behavioral changes unless requested.

## Maintainability Viewpoints

Check code against:

- readability: names and structure reveal intent
- cohesion: each module has a clear responsibility
- coupling: dependencies point in the intended direction
- testability: behavior can be verified without excessive setup
- compatibility: public contracts are stable or migration is documented
- error handling: failures are explicit and actionable
- observability: logs and diagnostics are useful and safe
- performance: obvious inefficient paths are avoided in critical flows
- deletion safety: removed behavior is intentional and documented

## Design Rules

- Prefer existing project patterns over new local inventions.
- Keep functions and classes small enough to review.
- Separate domain logic from transport, UI, persistence, and infrastructure.
- Avoid broad utility modules unless the project already uses that pattern.
- Make boundary conversions explicit.
- Keep generated code separate from hand-written code.

## Language-Specific Rules

Common standards define the intent. Language-specific details belong in
profiles under `standards/profiles/` or downstream project rules.

Examples:

- Python formatting, typing, and package rules belong in the Python profile or
  project `.ai/project/COMMANDS.yml`.
- TypeScript strictness, build, and package-manager rules belong in the
  TypeScript profile or project `.ai/project/COMMANDS.yml`.

## Comments

Use comments sparingly. Add them when they explain:

- non-obvious design constraints
- compatibility requirements
- security-sensitive decisions
- complex algorithms or state transitions

Do not add comments that only narrate simple assignments or obvious control
flow.

## Generated Code

Generated files must be clearly identified. If generated output is committed,
the generator command and source input must be documented.
