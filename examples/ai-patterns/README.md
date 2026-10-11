# AI Reference Patterns: canonical fixtures

The Format 1.0 specification remains authoritative. This catalog extends the
existing Assistant Prompt Profile; it does not add grammar, APIs, or automatic
execution. All people, IDs, and dates in new fixtures are fictional supplied
context, not inferred metadata for a real workspace.

## Sources of truth

- `manifest.json` maps stable PAT IDs to context, provenance, independent
  fixture files, diagnostic expectations and actual observations, and JA/EN
  documentation sections. Planned entries have `validation: "not run"`.
- `<PAT-ID>/recommended.life.txt` is canonical code. Counterexamples live in
  separate files in the same directory. Never concatenate unrelated cases.
- JA/EN descriptions share identical code. Named HTML comments identify each
  copied fence; the offline checker rejects a changed or missing copy.
- Each entry has input, context, reason, spec links, source links, and an
  implementer semantic review. The latter is not independent approval or an
  LLM evaluation. Raw input language remains unchanged in both documents.

The 68 planned slots are grouped as TYPE 9, STATUS 7, TIME 10, REC 8, REL 8,
GRAM 8, COM 8, PIT 10. A slot means one distinct interpretation, not one line.
File-level examples include required context/headers. Codes and document
headers are not always suitable for blind appending to an existing workspace.

## Validation

```sh
python scripts/check_ai_patterns.py --allow-planned --output .cache/ai-patterns.json
python -m unittest tests.test_ai_patterns tests.test_ai_prompt_profile
```

`--allow-planned` is for intermediate child PRs only. It lists unimplemented
slots as not run; it never counts them as passed. The final catalog gate is:

```sh
python scripts/check_ai_patterns.py --output .cache/ai-patterns-final.json
```

The checker calls the existing `python -m lifetxt check <fixture> --format json`
separately for each fixture. It records command, engine commit, Core version,
UTF-8 input hash, exit, full diagnostics, and stderr; warning exit 0 is not a
clean result. Stored observations in the manifest identify the Core source
commit used when authoring, not a future documentation commit. New runs record
their current checkout separately. No successful result is written over the
fixtures or expectations automatically. Fixed-range recurrence queries also
compare their full agenda JSON. Runs use UTC and never use `now`.

The checker selects `validation.config.json` and `LIFETXT_TIMEZONE=UTC`
explicitly and clears inherited `LIFETXT_*` overrides. Subprocess text is UTF-8.
This keeps results independent of a contributor's personal config, language,
host timezone, and default console encoding; it does not edit that config.

Counterexamples: A = syntax error, B = validator warning, C = valid code with
wrong source meaning, D = unsupported capability claim. C and D can also carry
warnings; their meaning/capability label is not a prediction of diagnostics.
`check` cannot prove candidate-date exclusivity, successful approval, actual
notification delivery, or fidelity to a natural-language source.

## Maintenance

Update canonical files and both language copies together. Rerun Core, inspect
all diagnostic changes, and record observations before committing. Do not
invent dates/IDs/metadata to silence a warning. Preserve IDs through edits;
document any retirement without recycling the ID. Additions beyond the agreed
68 slots require updating the coverage contract and its reviewable task first.

No external LLM calls, credentials, live user files, paid services, or network
access are needed. External effectiveness observation is optional in #1164.
