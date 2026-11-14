# Typed JSON details and start conditions

Issue [#1594](https://github.com/Eruhitsuji/lifetxt/issues/1594) defines the scope. This is a Feature with High assurance. Review the parser and interchange first, followed by integration across dependency consumers.

## Compatibility

The life.txt grammar extension uses the whitespace-delimited `json<< ... >>` form, preserving existing strings such as `json:true`. An older parser reports an error on the new syntax. Older clients can also treat text `requires:` as an unknown custom key and omit its readiness effect. Use compatible clients for editing or evaluating conditions. Existing files need no migration. The rollback is a reviewed revert after retaining a copy of any files authored using the new values or conditions.

A top-level JSON array contributes its elements to the value list of any key. Nest an array once to store it as a single value. The in-memory representation and JSON/JSONL payload use arrays of occurrences with JSON values as elements. Structured CSV selects an explicit header containing a colon, which cannot collide with a valid native detail key. Standard keys expecting text keep their validation. Custom keys and `requires:` accept typed values.

Each requirement is evaluated from the same loaded ID universe as dependency blockers. A condition result may be true, false, or unknown. The same start condition is used by agenda and next-action views. Conditions are evaluated from current state and do not trigger state changes or establish historical facts.

## Review and verification

- Parser/interchange review covers legacy valid literals, malformed payloads, and nested value round trips.
- Integration review covers missing/ambiguous IDs, false versus unknown conditions, and legacy dependency behavior.
- Focused automated evidence is in `tests/test_json_details_requirements.py`. GitHub CI and independent implementation/integration review remain merge gates.
