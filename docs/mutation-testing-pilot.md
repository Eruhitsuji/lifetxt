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
