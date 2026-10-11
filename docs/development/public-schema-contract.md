# Public schema test contract

`tests/fixtures/public_schema_contract.json` is the reviewed public schema
inventory. Each filename records its versioned `$id` and a SHA-256 digest of
JSON serialized with sorted keys, compact separators and ASCII escaping.
Whitespace and key order changes do not change the digest.

`bundle` lists documents registered by the legacy CLI surfaces. `standalone`
explicitly lists published contracts outside that bundle: currently
`progress-delta-v1.schema.json`, exercised by `tests.test_progress_delta`.
Both distributions are checked; standalone documents are not added to runtime
registration or required to have a bundle sample by this change.

The fixture is independent of the runtime registry. Tests compare the exact
registered, published and sample filename sets, identifiers, schema contents,
and CLI output filenames against it. They also retain Draft 2020-12 validation
when its optional test dependencies are installed. No runtime dependency is
added and no public schema is changed by this contract.

When intentionally adding or changing a public schema:

1. Change its source definition, sample and published `dist/schemas` document.
2. Review the semantic change and its versioned identifier. Check compatibility
   before changing a public contract.
3. Update only the corresponding fixture entry after confirming that the
   generated and published documents match. Use `tests.schema_contract.schema_digest`
   on the reviewed document to calculate its digest. Do not regenerate the
   entire inventory automatically during tests or CI.
4. Run `python -m unittest tests.test_public_schema_contract
   tests.test_schema_extensions_v2 tests.test_safety_cli`.
5. Include the source, publication, sample and fixture diffs in the same PR.

The initial fixture was captured only after verifying every generated document
against its published counterpart. Subsequent updates are intentional contract
reviews, rather than synchronizing several hardcoded counts.

The negative fixtures demonstrate additions, removals, equal-count replacement,
duplicate identifiers, changed versions, synchronized content changes,
publication drift and missing samples. An identical same-name registration
overwritten before the final dictionary is returned cannot be observed by these
tests; redesigning registration is outside this change.
