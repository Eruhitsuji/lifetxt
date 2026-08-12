# Initial Static-Typing Boundary

Issue #345 selects `lifetxt/diagnostic_contract.py` as the first static-typing
boundary. This module is shared by CLI, Web, and MCP output paths, and its
diagnostic JSON shape is a stable internal contract with a high payoff from
refactor checking.

## Tool policy

The project uses mypy `>=1.13,<2` as a development-only dependency. The local
command is:

```console
mypy --follow-imports=skip --ignore-missing-imports lifetxt/diagnostic_contract.py
```

The command is intentionally narrower than `mypy lifetxt`. Runtime users do not
install mypy, and the dependency-free package remains unchanged.

## Boundary rules

- #346 may add annotations and compatible helper types only in
  `lifetxt/diagnostic_contract.py` and its focused tests.
- The first implementation should enable checking of the module's function
  bodies and return values, with strictness increased only where the module is
  annotated enough to produce useful diagnostics.
- Untyped legacy diagnostic objects are accepted at the boundary through a
  small protocol or typed adapter; the checker must not require annotations in
  their defining modules.
- Web, MCP, parser, and CLI callers remain outside the checked boundary until a
  separate issue expands it with evidence.

## Expansion rule

After #346 is green, expand by one directly dependent contract at a time. Each
expansion must name its files, preserve the public JSON shape, keep the command
passing without broad suppressions, and record the incremental benefit. A
repository-wide annotation conversion is explicitly not a goal of this phase.

## Implementation target

#346 should add the first annotations, focused contract tests, and the blocking
CI invocation for this file. It must not change runtime behavior or make mypy a
normal installation dependency.
