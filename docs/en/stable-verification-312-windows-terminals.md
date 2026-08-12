# Dependency-Free TUI Windows Terminal Verification

Issue: #312

## Environments

Run the documented dependency-free TUI start path in a supported WSL
distribution and native Windows Terminal. Record OS/build, terminal version,
locale, code page, Python version, terminal dimensions, and whether the run is
interactive or redirected.

## Scenarios

Exercise ASCII/Unicode fallback, non-ASCII paths/content, narrow layout,
editor suspend/resume, Ctrl-C, auto-reload, revision refresh, timezone display,
semantic conflict, multi-file transaction, attachment/work-session status,
stale-lock guidance, and interrupted-operation recovery.

## Evidence

For each scenario capture expected/observed result, exit status, and a redacted
screen/log reference. Unsupported glyph or terminal behavior must be recorded
in the support matrix rather than silently treated as pass. This document is a
runbook; no WSL or native Terminal execution result is claimed here.
