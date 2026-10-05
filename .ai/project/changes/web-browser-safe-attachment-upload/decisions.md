# Decisions

- Human request explicitly authorizes #1095 implementation/self-review/PR. Issue comment concretizes endpoint, cap, M scope and readiness before edits; High human security/merge review remains required. No further account, deployment or merge action.
- M justification: receipt/bounds/managed path/CAS are one safety boundary; splitting runtime implementation would expose an incomplete upload entry point. Complexity 8 escalated to High, with targeted negative and failure tests.
- Reuse existing transaction/MIME/executable/revision primitives; no second writer.
- Raw body rather than multipart/Base64: avoids new dependency and parser materialization. Fixed 10 MiB Web cap uses existing limits; no config-setting expansion.
- Receipt UUID rather than speculative att:v1 resolver: #1099 is reviewed design guidance, not automatic approval of #1100/#1101. Those contracts are non-blocking to a path-free local upload receipt.
- No blanket legacy item/MCP redaction: compatibility preserves operator raw representation. All-surface future resource projection stays #1100.
- Post-Stable 1.0.3 feature request/security hardening of existing generic upload capability; historical first-Stable freeze is not used to require another approval of this explicit task. Parent #1094 and historical stabilization tracker #283 remain referenced; no release/deployment performed.
- Alternatives deferred: upload UX #1096, transport deployment policy #1097, at-rest copies/evidence #1098, global projection #1100, resolver #1101, cloud profiles #1102, SSRF import #1103.
- Self-review corrections: bounded bytearray for tiny-chunk overhead; duplicate contract headers refused; cancellation cannot free commit slot early. Further findings and final verification recorded in verification.yml.

- Final self-review also makes generated-source policy discovery non-writable and rejects additional Mach-O fat signatures. Upload worker cancellation/deadline, schema/OpenAPI and MIME classifications have targeted coverage.
- Initial full test run failed 4 CLI subprocess cases because the checkout was not installed; repository setup command python -m pip install -e . resolved all 4. No product/test assertion was weakened for this environment failure. Schema count/set assertions were updated only for the newly registered 86th document.
