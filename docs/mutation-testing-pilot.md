# Mutation testing pilot

The bounded pilot targets `lifetxt.parser` and uses `mutmut` as an optional
 development dependency. It is intentionally manual and does not run in the
normal pull-request job.

```text
python -m pip install mutmut
mutmut run --paths-to-mutate lifetxt/parser.py --runner "python -m unittest tests.test_lifetxt tests.test_core_boundaries_884"
mutmut results
```

Record the run date, target, killed/surviving mutants, and classification of
survivors in the issue or change evidence. Genuine survivors become focused
regression tests; equivalent or unreachable mutants are documented. The pilot
is a periodic/manual audit recommendation, not a required perfect score.

## Pilot evidence (2026-09-23)

- Environment: Windows, Python 3.10.16 virtual environment `.venv-quality`.
- Tool: `mutmut 3.8.0` installed successfully.
- Target: `lifetxt/parser.py` with the focused unittest runner above.
- Result: mutmut refused to start because native Windows execution is not
  supported by the installed release. WSL was also unavailable in this
  environment (`E_ACCESSDENIED`). No mutation score is claimed.
- Decision: keep mutation testing as a manual/periodic WSL or Linux audit; do
  not add it to normal PR CI on Windows. The prerequisite and failure mode are
  now explicit and reproducible rather than silently skipped.